# Mystic Requirements Checklist

이 문서는 Mystic 프로젝트를 시작하기 위해 필요한 전체 목록이다.  
범위는 데이터셋, 서버/컴퓨팅, 로컬 장비, 계정, 소프트웨어, 저장소 구조, 학습 대상, 실행 순서다.

---

# 1. 수집해야 하는 데이터셋 리스트

| 순위 | 이름 | 중요도 | 수집 데이터 |
|---:|---|---|---|
| 1 | **Internal Mystic Data** | 최상 | `failed_proofs`, `raven_critiques`, `counterexamples`, `forge_experiments`, `lean_attempts`, `proof_repairs`, `attack_maps`, `routing_logs` |
| 2 | **NuminaMath-CoT** | 최상 | 수학 문제, CoT 풀이, 올림피아드/고등수학 문제풀이 |
| 3 | **OpenMathInstruct-2** | 최상 | 수학 instruction, 문제-풀이, code-interpreter 풀이 |
| 4 | **OpenMathInstruct-1** | 최상 | 수학 problem-solution pairs |
| 5 | **OpenThoughts3 / OpenThoughts2** | 최상 | math/code/science reasoning traces |
| 6 | **OpenR1 / Mixture-of-Thoughts** | 최상 | DeepSeek-R1식 verified reasoning traces |
| 7 | **AM-DeepSeek-R1-Distilled** | 최상 | distilled reasoning traces, 수학/코드 검증 reasoning |
| 8 | **LeanDojo** | 최상 | Lean proof states, tactics, premises |
| 9 | **LEAN-GitHub** | 최상 | Lean 4 theorem, tactic, proof corpus |
| 10 | **ProofNet** | 높음 | 자연어 theorem/proof + Lean formal statement |
| 11 | **miniF2F** | 높음 | formal olympiad theorem proving |
| 12 | **PutnamBench** | 높음 | Putnam급 formal theorem proving |
| 13 | **Proof-Pile / Proof-Pile-2** | 매우 높음 | formal math, theorem proving, scientific/math corpus |
| 14 | **The Stack v2 Python subset** | 매우 높음 | Python source code |
| 15 | **The Stack v2 Lean subset** | 매우 높음 | Lean/mathlib 관련 코드 |
| 16 | **The Stack v2 Sage/SymPy subset** | 매우 높음 | 수학 계산 코드 |
| 17 | **OpenCodeInstruct** | 매우 높음 | code instruction, solution, test cases, execution feedback |
| 18 | **CodeContests** | 매우 높음 | programming problems, solutions, tests |
| 19 | **APPS** | 높음 | 자연어 coding problem → Python solution |
| 20 | **TACO** | 높음 | algorithmic code generation, tests |
| 21 | **Codehacks** | 높음 | adversarial test/counterexample data |
| 22 | **SciCode** | 최상 | 과학 연구 코딩, math/physics/chem/bio/materials tasks |
| 23 | **OpenWebMath** | 최상 | 수학 웹 텍스트, LaTeX/math notation |
| 24 | **Nemotron-CC-Math** | 최상 | math/science pretraining corpus |
| 25 | **MegaMath** | 매우 높음 | math text, math code, synthetic QA |
| 26 | **FineMath** | 높음 | filtered math web corpus |
| 27 | **DeepSeekMath-style Corpus** | 최상 | Common Crawl 기반 math webpage corpus |
| 28 | **MetaMathQA** | 높음 | 변형 수학 QA, rephrased/forward/backward problems |
| 29 | **MathInstruct / MAmmoTH** | 매우 높음 | CoT + PoT 수학 instruction data |
| 30 | **MATH / MATH-500** | 높음 | competition math, step-by-step solutions |
| 31 | **HARP** | 높음 | AMC/AIME/USA(J)MO 수학 문제 |
| 32 | **OlympiadBench** | 높음 | 수학/물리 올림피아드 문제 |
| 33 | **Omni-MATH** | 높음 | 고난도 olympiad-level 수학 |
| 34 | **PRM800K** | 최상 | 수학 풀이 step-level correctness labels |
| 35 | **Math-Shepherd Data** | 높음 | process supervision math data |
| 36 | **FLAN Collection** | 높음 | instruction following, CoT/few-shot/zero-shot tasks |
| 37 | **Tülu 3 Datasets** | 높음 | SFT/preference/instruction data |
| 38 | **CoT Collection** | 높음 | multi-task chain-of-thought rationales |
| 39 | **Dolma math/science/code subset** | 높음 | web, academic, code, books 중 math/science/code |
| 40 | **DCLM math/science/code subset** | 매우 높음 | high-quality filtered web corpus |
| 41 | **RedPajama subset** | 중간~높음 | LLaMA-style open pretraining corpus subset |
| 42 | **SlimPajama subset** | 중간~높음 | cleaned RedPajama subset |
| 43 | **The Pile subset** | 중간 | academic/code/web/books subset |
| 44 | **FineWeb subset** | 중간~높음 | cleaned web corpus 중 math/science/code |
| 45 | **Common Crawl filtered subset** | 최상 | 자체 math/science/code 필터링 원천 |
| 46 | **C4 / mC4 subset** | 높음 | cleaned web text |
| 47 | **RefinedWeb subset** | 높음 | high-quality web text |
| 48 | **Wikipedia / Wikidata** | 높음 | 백과 지식, 구조화 지식 graph |
| 49 | **StackExchange Dumps** | 최상 | Math StackExchange, Physics, CS, Stack Overflow Q&A |
| 50 | **arXiv source / LaTeX subset** | 최상 | 수학/물리/CS 논문 LaTeX source |
| 51 | **S2ORC** | 최상 | 학술 논문 full text, abstracts, citations |
| 52 | **Semantic Scholar Open Data** | 높음 | paper metadata, citation graph, author graph |
| 53 | **arXiv Metadata + Paper Subset** | 높음 | 수학/물리/CS 논문 metadata/full text |
| 54 | **GPQA / GPQA Diamond** | 높음 | graduate-level biology/physics/chemistry QA |
| 55 | **SciBench** | 높음 | 대학 수준 수학/물리/화학 문제 |
| 56 | **LAB-Bench** | 중간~높음 | biology research, literature reasoning, database navigation |
| 57 | **MSQA / Materials Science QA** | 중간~높음 | 재료과학 QA |
| 58 | **SciFIBench** | 중간 | scientific figure interpretation |
| 59 | **ToolBench** | 높음 | tool-use instruction, API call path |
| 60 | **Gorilla / APIBench** | 중간~높음 | API 호출 정확도, tool-use data |
| 61 | **AgentBench** | 중간 | multi-turn agent task/environment data |
| 62 | **SWE-bench** | 높음 | GitHub issue → patch → test pass |
| 63 | **SWE-bench Verified** | 높음 | human-verified SWE-bench subset |
| 64 | **Open-SWE-Traces** | 높음 | agentic software engineering trajectories |
| 65 | **HumanEval / MBPP / MBPP+** | 중간 | Python coding eval/training |
| 66 | **LiveCodeBench** | 높음 | contamination 적은 coding benchmark |
| 67 | **BigCodeBench** | 높음 | realistic code generation |
| 68 | **NaturalProofs** | 중간~높음 | 자연어 theorem/proof corpus |
| 69 | **Isabelle AFP Dataset** | 중간 | Isabelle formal proof corpus |
| 70 | **CoqGym** | 중간 | Coq proof states/tactics |
| 71 | **HolStep** | 중간 | HOL theorem proving steps |
| 72 | **DeepSeek-Prover Data** | 높음 | Lean formal proof synthetic/prover data |
| 73 | **AlphaGeometry Synthetic Geometry Data** | 높음 | synthetic geometry theorem/proof data |
| 74 | **GSM8K** | 중간 | grade-school math CoT |
| 75 | **AQUA-RAT** | 중간 | algebraic word problems + rationales |
| 76 | **ScienceQA** | 중간 | science QA |
| 77 | **ARC-Challenge** | 중간 | science reasoning baseline |
| 78 | **MMLU-Pro** | 중간~높음 | broad academic reasoning |
| 79 | **HLE / Humanity’s Last Exam** | 평가용 최상 | expert-level broad benchmark |
| 80 | **FrontierMath** | 평가용 최상 | 연구급 수학 문제 |

---

# 2. 서버 / 컴퓨팅 리스트 — 무료 우선

| 순위 | 이름 | 비용 | 용도 |
|---:|---|---|---|
| 1 | **로컬 PC** | 이미 있으면 무료 | 데이터 정리, Archive, Python/SymPy/Lean, 작은 모델 테스트 |
| 2 | **Google Colab Free** | 무료 | 작은 GPU 실험, notebook, 소형 QLoRA 테스트 |
| 3 | **Kaggle Notebooks** | 무료 | 무료 GPU notebook, 데이터 실험, 작은 모델 테스트 |
| 4 | **GitHub Codespaces** | 무료 quota 있음 | 코드 개발, repo 테스트, CPU 개발 환경 |
| 5 | **Oracle Cloud Always Free** | 무료 tier | 항상 켜는 CPU VPS, API/DB/scheduler |
| 6 | **Lightning AI Free Tier** | 무료 credit/시간 있음 | 짧은 GPU/Studio 실험 |
| 7 | **Modal Free Credits** | 무료 credit | serverless GPU/CPU burst 실험 |
| 8 | **Saturn Cloud Free Tier** | 무료 tier | notebook/ML 실험 |
| 9 | **Hugging Face Spaces Free CPU** | 무료 CPU 가능 | 데모 UI, 가벼운 API |
| 10 | **RunPod Community Cloud** | 유료 저가 | RTX 3090/4090 짧은 학습 |
| 11 | **Vast.ai** | 유료 저가 | 저가 GPU burst |
| 12 | **Paperspace / Gradient** | 유료/무료 변동 | notebook/GPU 실험 |
| 13 | **AWS/GCP/Azure Free Tier** | GPU는 보통 무료 아님 | CPU/스토리지 실험 |
| 14 | **Lambda Labs** | 유료 | 안정적 GPU 학습 |
| 15 | **CoreWeave / Crusoe / Lambda류 GPU Cloud** | 유료 | 나중에 대형 학습 |

---

# 3. 로컬 장비 리스트

| 항목 | 최소 | 권장 |
|---|---:|---:|
| CPU | i5 / Ryzen 5급 | i7 / Ryzen 7 이상 |
| RAM | 16GB | 32GB~64GB |
| SSD | 1TB | 2TB~4TB |
| GPU | 없어도 됨 | NVIDIA 12GB+ 있으면 좋음 |
| OS | Windows 가능 | Linux / WSL2 권장 |
| 백업 | 외장 SSD 1개 | 외장 SSD + 클라우드 |

---

# 4. 계정 리스트

| 순위 | 계정 | 용도 |
|---:|---|---|
| 1 | **GitHub** | 코드 저장, Codespaces, version control |
| 2 | **Hugging Face** | 모델/데이터셋 다운로드, adapter 업로드 |
| 3 | **Google 계정** | Colab, Drive 백업 |
| 4 | **Kaggle 계정** | 무료 GPU notebook, 데이터셋 |
| 5 | **Oracle Cloud 계정** | 무료 CPU VPS |
| 6 | **RunPod / Vast.ai 계정** | 저가 GPU burst |
| 7 | **Weights & Biases** | 학습 로그/평가 기록 |
| 8 | **Docker Hub** | container image 저장 |
| 9 | **Modal / Lightning AI 계정** | 무료 credit 실험 |
| 10 | **Cloudflare 계정** | 나중에 API/도메인/터널 |

---

# 5. 필수 소프트웨어 리스트

| 순위 | 이름 | 용도 |
|---:|---|---|
| 1 | **Python 3.11+** | 전체 백엔드/도구 |
| 2 | **Git** | 버전 관리 |
| 3 | **Docker** | 재현 가능한 실행환경 |
| 4 | **VS Code / Cursor / Codex CLI** | 개발 |
| 5 | **SQLite** | 초기 Archive DB |
| 6 | **PostgreSQL** | 나중에 본 DB |
| 7 | **Qdrant / Chroma / pgvector** | vector search |
| 8 | **Ollama** | 로컬 모델 실행 |
| 9 | **llama.cpp** | GGUF/CPU 추론 |
| 10 | **Transformers** | 모델 로딩/학습 |
| 11 | **PEFT** | LoRA |
| 12 | **Unsloth** | QLoRA 저비용 학습 |
| 13 | **Axolotl** | 학습 config 관리 |
| 14 | **TRL** | DPO/RLHF류 학습 |
| 15 | **PyTorch** | 모델 학습 |
| 16 | **FastAPI** | API 서버 |
| 17 | **Typer** | CLI |
| 18 | **SQLAlchemy** | DB ORM |
| 19 | **Pydantic** | 데이터 스키마 |
| 20 | **pytest** | 테스트 |
| 21 | **SymPy** | 수학 계산 |
| 22 | **NumPy / SciPy** | 계산 |
| 23 | **SageMath** | 고급 수학 계산 |
| 24 | **Lean 4** | formal proof |
| 25 | **Z3** | SMT/SAT 검증 |
| 26 | **Jupyter** | 실험 notebook |
| 27 | **DVC** | 데이터 버전 관리 |
| 28 | **rclone** | 클라우드 백업 |
| 29 | **Weights & Biases** | 실험 기록 |
| 30 | **MLflow** | 실험 관리 대안 |

---

# 6. 저장소 / 폴더 구조

```text
mystic/
├── README.md
├── CODEX_PROMPT.md
├── docs/
├── configs/
├── mystic/
├── scripts/
├── tests/
└── data/
```

```text
mystic_data/
├── raw/
├── processed/
├── verified/
├── rejected/
├── needs_review/
├── train_ready/
├── eval_holdout/
├── exports/
├── models/
├── adapters/
├── logs/
└── metadata/
```

---

# 7. 학습 대상 리스트

| 순위 | 모델/Adapter | 먼저 필요한 데이터 |
|---:|---|---|
| 1 | **Raven-LoRA** | failed proofs, critiques, accepted/rejected pairs |
| 2 | **Forge-LoRA** | code tasks, Python experiments, execution logs |
| 3 | **Prime-LoRA** | NuminaMath, OpenMathInstruct, OpenR1, Raven-corrected math |
| 4 | **Lean-LoRA** | LeanDojo, LEAN-GitHub, ProofNet, Lean error logs |
| 5 | **Core-Router-LoRA** | routing logs, domain labels, session success/failure |
| 6 | **Pattern-LoRA** | pattern discovery logs, sequence/modular data |
| 7 | **Physics-LoRA** | GPQA, SciBench, SciCode, physics notes |
| 8 | **Chem-LoRA** | GPQA, chemistry QA, SciCode |
| 9 | **BioMath-LoRA** | LAB-Bench, biology QA, sequence/database tasks |
| 10 | **Report-LoRA** | final reports, structured summaries |

---

# 8. 실행 순서 리스트

| 순서 | 할 일 |
|---:|---|
| 1 | GitHub repo 만들기 |
| 2 | 로컬 `mystic/`, `mystic_data/` 폴더 만들기 |
| 3 | Python/SQLite/SymPy/Lean/Ollama 설치 |
| 4 | JSONL 스키마 만들기 |
| 5 | Internal Mystic Data 파일 만들기 |
| 6 | NuminaMath-CoT 일부 수집 |
| 7 | OpenMathInstruct 일부 수집 |
| 8 | OpenThoughts/OpenR1 일부 수집 |
| 9 | LeanDojo/ProofNet 일부 수집 |
| 10 | The Stack v2 Python/Lean subset 수집 |
| 11 | Archive DB 만들기 |
| 12 | Raven prompt evaluator 만들기 |
| 13 | Forge Python runner 만들기 |
| 14 | Python/SymPy 검증 로그 저장 |
| 15 | Lean runner 만들기 |
| 16 | Dataset exporter 만들기 |
| 17 | Raven-LoRA 첫 학습 |
| 18 | Forge-LoRA 첫 학습 |
| 19 | Prime-LoRA 첫 학습 |
| 20 | Evaluator 만들기 |
| 21 | Model registry 만들기 |
| 22 | Scheduler 붙이기 |
| 23 | 원격 GPU burst 학습 자동화 |
| 24 | v0.1 report/dashboard 만들기 |

---

# 9. 지금 당장 최소 세트

## 데이터

```text
1. Internal Mystic Data
2. NuminaMath-CoT
3. OpenMathInstruct
4. OpenThoughts/OpenR1
5. LeanDojo/ProofNet
6. The Stack v2 Python/Lean subset
7. SciCode
```

## 서버

```text
1. 로컬 PC
2. Google Colab Free
3. Kaggle Notebooks
4. GitHub Codespaces
5. Oracle Always Free
```

## 소프트웨어

```text
1. Python
2. Git
3. SQLite
4. SymPy
5. Lean 4
6. Ollama
7. Transformers
8. PEFT/Unsloth
9. FastAPI/Typer
10. pytest
```

## 장비

```text
1. RAM 16GB 이상
2. SSD 1TB 이상
3. 외장 SSD 또는 클라우드 백업
```

---

# 10. 핵심 결론

처음에는 다음 조합으로 시작한다.

```text
로컬 PC
+ 무료 notebook GPU
+ 공개 seed 데이터
+ Internal Mystic Data 저장소
```

GPU 서버는 Raven/Forge/Prime LoRA 학습할 때만 잠깐 사용한다.
