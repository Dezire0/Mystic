from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "discord.py is not installed. Run `.venv-training/bin/python -m pip install -r requirements-discord.txt` first."
    ) from exc

from mystic.discord_dashboard import (
    ExpertSnapshot,
    expert_detail_page,
    load_dashboard_snapshot,
    overview_page,
    save_subscriber,
)
from mystic.env_loader import load_dotenv_file
from mystic.research_lab import ResearchResult, run_research_lab


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Mystic Discord DM dashboard bot.")
    parser.add_argument("--base-dir", default=str(ROOT / "mystic_data"))
    parser.add_argument("--token-env", default="MYSTIC_DISCORD_TOKEN")
    parser.add_argument("--guild-id", type=int, default=0, help="Optional guild id for faster command sync during setup.")
    return parser


def embed_from_payload(payload: dict[str, object]) -> discord.Embed:
    color = int(payload.get("color", 0x5865F2))
    embed = discord.Embed(
        title=str(payload.get("title", "")),
        description=str(payload.get("description", "")),
        color=color,
    )
    author = str(payload.get("author", "") or "")
    if author:
        embed.set_author(name=author)
    for field in payload.get("fields", []):
        embed.add_field(
            name=str(field.get("name", "-")),
            value=str(field.get("value", "-"))[:1024],
            inline=bool(field.get("inline", False)),
        )
    footer = str(payload.get("footer", "") or "")
    if footer:
        embed.set_footer(text=footer[:2048])
    return embed


def chunk_text(value: str, limit: int = 3900) -> list[str]:
    text = value.strip()
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_index = text.rfind("\n", 0, limit)
        if split_index <= 0:
            split_index = limit
        chunks.append(text[:split_index].strip())
        text = text[split_index:].strip()
    return chunks


def compact_line(value: str, limit: int = 220) -> str:
    text = " ".join(value.strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def research_embed(result: ResearchResult) -> discord.Embed:
    embed = discord.Embed(
        title=f"Mystic 연구실 · {result.specialist_name}",
        description=chunk_text(result.final_answer)[0],
        color=0x5865F2,
    )
    embed.add_field(name="선택 전문가", value=result.specialist_name, inline=True)
    embed.add_field(
        name="참여 전문가",
        value=", ".join(result.participating_specialists)[:1024] or "-",
        inline=False,
    )
    embed.add_field(name="생성 모델", value=f"{result.backend} / {result.model}"[:1024], inline=True)
    embed.add_field(name="검증 모델", value=f"{result.critic_backend} / {result.critic_model}"[:1024], inline=True)
    embed.add_field(name="전략", value=(result.plan_strategy or "-")[:1024], inline=False)
    embed.add_field(
        name="Raven 판정",
        value=f"{result.critic_verdict} (confidence={result.critic_confidence:.2f})"[:1024],
        inline=True,
    )
    if result.critic_first_fatal_error:
        embed.add_field(name="검증 메모", value=result.critic_first_fatal_error[:1024], inline=False)
    return embed


def is_dm_message(message: Any) -> bool:
    return isinstance(getattr(message, "channel", None), discord.DMChannel)


def normalize_message_question(*, content: str, bot_user_id: int, is_dm: bool) -> str:
    text = content.strip()
    if not text:
        return ""
    if is_dm:
        return text
    for mention in (f"<@{bot_user_id}>", f"<@!{bot_user_id}>"):
        text = text.replace(mention, " ")
    return " ".join(text.split()).strip()


async def send_research_response(
    destination: discord.abc.Messageable,
    *,
    question: str,
    base_dir: Path,
) -> None:
    await destination.send(f"1. 질문 이해 중\n질문: {compact_line(question, 260)}")

    progress_queue: asyncio.Queue[tuple[str, dict[str, str]] | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def progress_callback(stage: str, payload: dict[str, str]) -> None:
        loop.call_soon_threadsafe(progress_queue.put_nowait, (stage, payload))

    async def run_and_report() -> ResearchResult:
        return await asyncio.to_thread(
            run_research_lab,
            question,
            base_dir=base_dir,
            progress_callback=progress_callback,
        )

    task = asyncio.create_task(run_and_report())
    while True:
        if task.done() and progress_queue.empty():
            break
        try:
            item = await asyncio.wait_for(progress_queue.get(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
        if item is None:
            continue
        stage, payload = item
        if stage == "routing_complete":
            await destination.send(
                "2. 전략 수립 완료\n"
                f"전문가: {payload.get('specialist', '-')}\n"
                f"지원 전문가: {payload.get('support_specialists', '-')}\n"
                f"이유: {compact_line(payload.get('reason', '-'))}\n"
                f"전략: {compact_line(payload.get('strategy', '-'), 320)}"
            )
        elif stage == "specialist_complete":
            await destination.send(
                "3. specialist 초안 생성 완료\n"
                f"전문가 이름: {payload.get('specialist_name', '-')}\n"
                f"전문가 코드: {payload.get('agent', '-')}\n"
                f"이해: {compact_line(payload.get('understanding', '-'), 240)}\n"
                f"전략: {compact_line(payload.get('strategy', '-'), 240)}\n"
                f"결론 초안: {compact_line(payload.get('conclusion', '-'), 220)}"
            )
        elif stage == "synthesis_complete":
            await destination.send(
                "4. Core 종합 초안 생성 완료\n"
                f"전문가 이름: {payload.get('specialist_name', '-')}\n"
                f"이해: {compact_line(payload.get('understanding', '-'), 320)}\n"
                f"전략: {compact_line(payload.get('strategy', '-'), 320)}\n"
                f"풀이: {compact_line(payload.get('execution', '-'), 500)}\n"
                f"결론 초안: {compact_line(payload.get('conclusion', '-'), 240)}"
            )
        elif stage == "critique_complete":
            warning = payload.get("first_fatal_error", "").strip() or "치명적 오류는 바로 잡히지 않음"
            await destination.send(
                "5. Raven 검증 완료\n"
                f"판정: {payload.get('verdict', '-')}\n"
                f"신뢰도: {payload.get('confidence', '0.0')}\n"
                f"메모: {compact_line(warning, 320)}"
            )

    result = await task
    chunks = chunk_text(result.final_answer)
    await destination.send(embed=research_embed(result))
    for extra in chunks[1:]:
        await destination.send(extra[:1900])


class ExpertSelect(discord.ui.Select["MysticOverviewView"]):
    def __init__(self, page_experts: list[ExpertSnapshot]):
        options = [
            discord.SelectOption(
                label=expert.name[:100],
                value=expert.agent,
                description=f"{expert.progress_percent}% | {expert.status_text}"[:100],
                emoji=expert.status_emoji,
            )
            for expert in page_experts
        ]
        super().__init__(placeholder="전문가 선택", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.open_expert(interaction, self.values[0])


class MysticOverviewView(discord.ui.View):
    def __init__(self, *, base_dir: Path, user_id: int, page: int = 0):
        super().__init__(timeout=900)
        self.base_dir = base_dir
        self.user_id = user_id
        self.page = page
        self.snapshot = load_dashboard_snapshot(base_dir)
        payload = overview_page(self.snapshot, page)
        self.page = int(payload["page"])
        self._refresh_select()

    def _refresh_select(self) -> None:
        self.clear_items()
        payload = overview_page(self.snapshot, self.page)
        page_experts = payload["page_experts"]
        if page_experts:
            self.add_item(ExpertSelect(page_experts))
        self.add_item(OverviewPrevButton())
        self.add_item(OverviewNextButton())
        self.add_item(OverviewRefreshButton())

    def current_payload(self) -> dict[str, object]:
        return overview_page(self.snapshot, self.page)

    async def open_expert(self, interaction: discord.Interaction, agent: str) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 대시보드는 요청자 전용입니다.", ephemeral=True)
            return
        detail_view = MysticExpertDetailView(base_dir=self.base_dir, user_id=self.user_id, agent=agent, page=self.page)
        await interaction.response.edit_message(embed=embed_from_payload(detail_view.current_payload()), view=detail_view)

    async def move(self, interaction: discord.Interaction, delta: int) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 대시보드는 요청자 전용입니다.", ephemeral=True)
            return
        total_pages = int(self.snapshot["total_pages"])
        self.page = max(0, min(self.page + delta, total_pages - 1))
        self.snapshot = load_dashboard_snapshot(self.base_dir)
        self._refresh_select()
        await interaction.response.edit_message(embed=embed_from_payload(self.current_payload()), view=self)

    async def refresh(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 대시보드는 요청자 전용입니다.", ephemeral=True)
            return
        self.snapshot = load_dashboard_snapshot(self.base_dir)
        self._refresh_select()
        await interaction.response.edit_message(embed=embed_from_payload(self.current_payload()), view=self)


class OverviewPrevButton(discord.ui.Button["MysticOverviewView"]):
    def __init__(self) -> None:
        super().__init__(label="이전", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.move(interaction, -1)


class OverviewNextButton(discord.ui.Button["MysticOverviewView"]):
    def __init__(self) -> None:
        super().__init__(label="다음", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.move(interaction, 1)


class OverviewRefreshButton(discord.ui.Button["MysticOverviewView"]):
    def __init__(self) -> None:
        super().__init__(label="새로고침", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.refresh(interaction)


class MysticExpertDetailView(discord.ui.View):
    def __init__(self, *, base_dir: Path, user_id: int, agent: str, page: int):
        super().__init__(timeout=900)
        self.base_dir = base_dir
        self.user_id = user_id
        self.agent = agent
        self.page = page
        self.snapshot = load_dashboard_snapshot(base_dir)
        self.add_item(DetailBackButton())
        self.add_item(DetailRefreshButton())

    def current_payload(self) -> dict[str, object]:
        return expert_detail_page(self.snapshot, self.agent)

    async def go_back(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 대시보드는 요청자 전용입니다.", ephemeral=True)
            return
        overview = MysticOverviewView(base_dir=self.base_dir, user_id=self.user_id, page=self.page)
        await interaction.response.edit_message(embed=embed_from_payload(overview.current_payload()), view=overview)

    async def refresh(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 대시보드는 요청자 전용입니다.", ephemeral=True)
            return
        self.snapshot = load_dashboard_snapshot(self.base_dir)
        await interaction.response.edit_message(embed=embed_from_payload(self.current_payload()), view=self)


class DetailBackButton(discord.ui.Button["MysticExpertDetailView"]):
    def __init__(self) -> None:
        super().__init__(label="목록으로", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.go_back(interaction)


class DetailRefreshButton(discord.ui.Button["MysticExpertDetailView"]):
    def __init__(self) -> None:
        super().__init__(label="새로고침", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await self.view.refresh(interaction)


class MysticDiscordBot(commands.Bot):
    def __init__(self, *, base_dir: Path, guild_id: int = 0):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.base_dir = base_dir
        self.guild_id = guild_id

    async def setup_hook(self) -> None:
        if self.guild_id > 0:
            guild = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or self.user is None:
            return

        in_dm = is_dm_message(message)
        if not in_dm and not self.user.mentioned_in(message):
            await self.process_commands(message)
            return

        question = normalize_message_question(
            content=message.content,
            bot_user_id=self.user.id,
            is_dm=in_dm,
        )
        if not question:
            await message.channel.send("질문 내용을 함께 보내 주세요.")
            await self.process_commands(message)
            return

        async with message.channel.typing():
            try:
                await send_research_response(message.channel, question=question, base_dir=self.base_dir)
            except Exception as exc:
                await message.channel.send(f"연구실 실행 실패: {exc}")
        await self.process_commands(message)


def register_commands(bot: MysticDiscordBot) -> None:
    @bot.tree.command(name="mystic", description="Mystic 학습 대시보드를 DM으로 엽니다.")
    async def mystic_dashboard(interaction: discord.Interaction) -> None:
        user = interaction.user
        save_subscriber(bot.base_dir, user_id=user.id, username=str(user))
        try:
            dm_channel = await user.create_dm()
            view = MysticOverviewView(base_dir=bot.base_dir, user_id=user.id, page=0)
            await dm_channel.send(embed=embed_from_payload(view.current_payload()), view=view)
        except discord.Forbidden:
            await interaction.response.send_message("DM을 열 수 없습니다. 디엠 허용을 켜 주세요.", ephemeral=True)
            return

        if interaction.guild is not None:
            await interaction.response.send_message("Mystic 대시보드를 DM으로 보냈습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("Mystic 대시보드를 보냈습니다.", ephemeral=False)

    @bot.tree.command(name="mystic_refresh", description="현재 DM에 새 Mystic 대시보드를 다시 보냅니다.")
    async def mystic_refresh(interaction: discord.Interaction) -> None:
        user = interaction.user
        save_subscriber(bot.base_dir, user_id=user.id, username=str(user))
        dm_channel = await user.create_dm()
        view = MysticOverviewView(base_dir=bot.base_dir, user_id=user.id, page=0)
        await dm_channel.send(embed=embed_from_payload(view.current_payload()), view=view)
        await interaction.response.send_message("최신 Mystic 대시보드를 DM으로 다시 보냈습니다.", ephemeral=True)

    @bot.tree.command(name="mystic_lab", description="Mystic 연구실로 수학 질문을 분석합니다.")
    @app_commands.describe(question="자연어 수학 질문")
    async def mystic_lab(interaction: discord.Interaction, question: str) -> None:
        if not question.strip():
            await interaction.response.send_message("질문이 비어 있습니다.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True, ephemeral=interaction.guild is not None)
        try:
            result = await asyncio.to_thread(run_research_lab, question.strip(), base_dir=bot.base_dir)
        except Exception as exc:
            await interaction.followup.send(f"연구실 실행 실패: {exc}", ephemeral=True)
            return

        chunks = chunk_text(result.final_answer)
        embed = research_embed(result)
        if interaction.guild is not None:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=False)
        for extra in chunks[1:]:
            await interaction.followup.send(extra[:1900], ephemeral=interaction.guild is not None)


async def run_bot(args: argparse.Namespace) -> None:
    token = getenv_required(args.token_env)
    bot = MysticDiscordBot(base_dir=Path(args.base_dir), guild_id=int(args.guild_id))
    register_commands(bot)
    await bot.start(token)


def getenv_required(name: str) -> str:
    import os

    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main(argv: list[str] | None = None) -> int:
    load_dotenv_file(ROOT / ".env", override=False)
    args = build_parser().parse_args(argv)
    asyncio.run(run_bot(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
