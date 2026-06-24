# Mystic Architecture-Aligned Training Plan

This plan follows `mystic_v0_1_architecture_canvas.md` instead of collapsing Mystic into one generic model.
Even when two agents use the same base model, the code structure and future adapter path remain separate.

## Current Local Snapshot

- Numina raw rows: `1100`
- Raven critiques rows: `10`
- Failed proofs rows: `8`
- Raven LoRA export rows: `10`
- Raven train rows: `9`
- Raven eval rows: `1`

## Architecture Targets

1. Mystic-Core - model `qwen3-14b` - adapter `none`
   Division: Core
   Implementation priority: 1
   Current stage: planning_only
   Checklist datasets: Internal Mystic Data, NuminaMath-CoT, OpenMathInstruct-2, OpenThoughts3 / OpenThoughts2, OpenR1 / Mixture-of-Thoughts, FLAN Collection, Tulu 3 Datasets, CoT Collection, ToolBench, AgentBench, StackExchange Dumps, Wikipedia / Wikidata
   Training plan: Train the router and orchestration policy from routing logs, attack maps, math/science instruction traces, and explicit tool-routing examples. Keep the model role separate even when it shares the same provider as other agents.

2. Mystic-Prime - model `deepseek-r1-distill-14b` - adapter `prime_lora_v0`
   Division: Pure Math
   Implementation priority: 2
   Current stage: planning_only
   Checklist datasets: Internal Mystic Data, NuminaMath-CoT, OpenMathInstruct-2, OpenMathInstruct-1, OpenThoughts3 / OpenThoughts2, OpenR1 / Mixture-of-Thoughts, AM-DeepSeek-R1-Distilled, OpenWebMath, Nemotron-CC-Math, MegaMath, DeepSeekMath-style Corpus, MetaMathQA, MathInstruct / MAmmoTH, MATH / MATH-500, HARP, OlympiadBench, Omni-MATH, PRM800K, Math-Shepherd Data
   Training plan: Start with Raven-corrected number-theory traces and verified solution chains, then expand to olympiad-style proof search and process-supervision math corpora.

3. Mystic-Algebra - model `qwen3-14b` - adapter `algebra_lora_v0`
   Division: Pure Math
   Implementation priority: 2
   Current stage: unconfigured
   Checklist datasets: NuminaMath-CoT, OpenMathInstruct-2, OpenMathInstruct-1, OpenThoughts3 / OpenThoughts2, OpenR1 / Mixture-of-Thoughts, OpenWebMath, MegaMath, FineMath, MetaMathQA, MathInstruct / MAmmoTH, MATH / MATH-500, PRM800K, Math-Shepherd Data
   Training plan: Specialize on symbolic manipulation, equation solving, and proof-structured algebra explanations. Build a dedicated adapter path even if the base model matches Prime.

4. Mystic-Geo - model `qwen3-14b` - adapter `geo_lora_v0`
   Division: Pure Math
   Implementation priority: 2
   Current stage: unconfigured
   Checklist datasets: NuminaMath-CoT, OpenMathInstruct-2, OpenWebMath, MATH / MATH-500, HARP, OlympiadBench, Omni-MATH, AlphaGeometry Synthetic Geometry Data, PRM800K, Math-Shepherd Data
   Training plan: Use geometry-heavy olympiad data plus synthetic theorem corpora to separate diagram-free reasoning, construction steps, and invariant-based proof critique.

5. Mystic-Analysis - model `qwen3-14b` - adapter `analysis_lora_v0`
   Division: Pure Math
   Implementation priority: 2
   Current stage: unconfigured
   Checklist datasets: NuminaMath-CoT, OpenMathInstruct-2, OpenR1 / Mixture-of-Thoughts, OpenWebMath, FineMath, DeepSeekMath-style Corpus, MathInstruct / MAmmoTH, MATH / MATH-500, OlympiadBench, PRM800K, Math-Shepherd Data
   Training plan: Focus on epsilon-delta arguments, convergence, inequalities, and functional estimates with strong process-supervision to reduce bluffing.

6. Mystic-Probability - model `qwen3-14b` - adapter `probability_lora_v0`
   Division: Pure Math
   Implementation priority: 2
   Current stage: unconfigured
   Checklist datasets: NuminaMath-CoT, OpenMathInstruct-2, OpenThoughts3 / OpenThoughts2, MegaMath, MathInstruct / MAmmoTH, MATH / MATH-500, PRM800K, Math-Shepherd Data, GSM8K, AQUA-RAT
   Training plan: Prioritize combinatorics, expectation, conditioning, and distribution reasoning with step-level correctness labels and conservative uncertainty handling.

7. Mystic-Logic - model `qwen3-14b` - adapter `logic_lora_v0`
   Division: Pure Math
   Implementation priority: 2
   Current stage: unconfigured
   Checklist datasets: LeanDojo, LEAN-GitHub, ProofNet, NaturalProofs, miniF2F, PutnamBench, HolStep, CoqGym, Isabelle AFP Dataset, DeepSeek-Prover Data
   Training plan: Separate informal logical reasoning from formal proof-state navigation. Use theorem-proving corpora plus natural proof datasets for contradiction detection and inference hygiene.

8. Mystic-Physics - model `qwen3-14b` - adapter `physics_lora_v0`
   Division: Science
   Implementation priority: 2
   Current stage: planning_only
   Checklist datasets: SciCode, GPQA / GPQA Diamond, SciBench, OlympiadBench, ScienceQA, ARC-Challenge, arXiv source / LaTeX subset, S2ORC, StackExchange Dumps
   Training plan: Train for mathematically grounded physics derivations, dimensional checks, and scientific coding traces before adding experiment or lab-heavy data.

9. Mystic-Complexity - model `qwen3-14b` - adapter `complexity_lora_v0`
   Division: Science
   Implementation priority: 2
   Current stage: unconfigured
   Checklist datasets: OpenCodeInstruct, CodeContests, APPS, TACO, SWE-bench, SWE-bench Verified, Open-SWE-Traces, The Stack v2 Python subset, StackExchange Dumps, arXiv source / LaTeX subset
   Training plan: Use algorithmic proofs, reductions, adversarial code tasks, and CS reasoning traces to specialize toward complexity-theory style explanation and counterexample search.

10. Mystic-BioMath - model `qwen3-14b` - adapter `biomath_lora_v0`
   Division: Science
   Implementation priority: 3
   Current stage: planning_only
   Checklist datasets: SciCode, GPQA / GPQA Diamond, LAB-Bench, ScienceQA, S2ORC, Semantic Scholar Open Data, StackExchange Dumps
   Training plan: Focus on quantitatively structured biology tasks, literature-grounded reasoning, and computational workflows rather than open-ended wet-lab generation.

11. Mystic-Chem - model `qwen3-14b` - adapter `chem_lora_v0`
   Division: Science
   Implementation priority: 3
   Current stage: planning_only
   Checklist datasets: SciCode, GPQA / GPQA Diamond, SciBench, MSQA / Materials Science QA, ScienceQA, S2ORC, arXiv source / LaTeX subset
   Training plan: Train for stoichiometric reasoning, symbolic chemistry derivations, and computational chemistry coding traces before broad chemistry QA expansion.

12. Mystic-Lean - model `qwen3-14b` - adapter `lean_lora_v0`
   Division: Verification
   Implementation priority: 2
   Current stage: planning_only
   Checklist datasets: LeanDojo, LEAN-GitHub, ProofNet, miniF2F, PutnamBench, Proof-Pile / Proof-Pile-2, The Stack v2 Lean subset, DeepSeek-Prover Data, Internal Mystic Data
   Training plan: Start with proof states, tactic prediction, and error repair. Use internal Lean attempts as failure-driven fine-tuning data after the first formal runner is stable.

13. Mystic-SMT - model `z3` - adapter `none`
   Division: Verification
   Implementation priority: 3
   Current stage: tool_only
   Checklist datasets: ToolBench, Gorilla / APIBench, AgentBench, APPS, TACO, HumanEval / MBPP / MBPP+, LiveCodeBench
   Training plan: Treat SMT as a tool-first component. Collect solver calls, satisfiable or unsatisfiable traces, and counterexample logs before considering any auxiliary adapter around solver orchestration.

14. Mystic-Raven - model `qwen3-14b` - adapter `raven_lora_v0`
   Division: Verification
   Implementation priority: 1
   Current stage: active_cycle
   Checklist datasets: Internal Mystic Data, NuminaMath-CoT, ProofNet, NaturalProofs, MATH / MATH-500, PRM800K, Math-Shepherd Data, miniF2F
   Training plan: Use failed proofs, critiques, repair attempts, and step-level correctness labels to train a conservative proof referee. Current real training path is the Qwen 0.5B Raven cycle on Kaggle.

15. Mystic-Forge - model `qwen3-coder` - adapter `forge_lora_v0`
   Division: Discovery
   Implementation priority: 1
   Current stage: planning_only
   Checklist datasets: Internal Mystic Data, The Stack v2 Python subset, The Stack v2 Sage/SymPy subset, OpenCodeInstruct, CodeContests, APPS, TACO, Codehacks, SciCode, ToolBench, SWE-bench, Open-SWE-Traces
   Training plan: Train code-first experiment generation, execution repair, and counterexample search. Internal forge experiments and Python runner logs are the highest-value future data source.

16. Mystic-Conjecture - model `qwen3-14b` - adapter `conjecture_lora_v0`
   Division: Discovery
   Implementation priority: 2
   Current stage: unconfigured
   Checklist datasets: NuminaMath-CoT, OpenMathInstruct-2, OpenThoughts3 / OpenThoughts2, OpenR1 / Mixture-of-Thoughts, OpenWebMath, MegaMath, MetaMathQA, MATH / MATH-500, HARP, OlympiadBench, StackExchange Dumps, arXiv source / LaTeX subset
   Training plan: Bias the model toward proposing candidate lemmas, reformulations, and attack directions rather than polished final proofs. Train separately from Prime and Pattern despite shared base models.

17. Mystic-Pattern - model `qwen3-14b` - adapter `pattern_lora_v0`
   Division: Discovery
   Implementation priority: 2
   Current stage: planning_only
   Checklist datasets: Internal Mystic Data, OpenWebMath, MegaMath, DeepSeekMath-style Corpus, MetaMathQA, MATH / MATH-500, PRM800K, Math-Shepherd Data, StackExchange Dumps
   Training plan: Train on invariants, recurrence behavior, modular patterns, and residue-class observations extracted from internal experiments and math corpora.

18. Mystic-Simulator - model `qwen3-coder` - adapter `simulator_lora_v0`
   Division: Discovery
   Implementation priority: 3
   Current stage: unconfigured
   Checklist datasets: The Stack v2 Python subset, The Stack v2 Sage/SymPy subset, OpenCodeInstruct, SciCode, ToolBench, Gorilla / APIBench, AgentBench, HumanEval / MBPP / MBPP+
   Training plan: Specialize on writing small numerical or symbolic simulators that support Forge and Raven verification loops. Start with execution stability and I/O discipline, not creativity.

19. Mystic-Archive - model `database` - adapter `none`
   Division: Memory
   Implementation priority: 1
   Current stage: tool_only
   Checklist datasets: Internal Mystic Data, Wikipedia / Wikidata, StackExchange Dumps, S2ORC, Semantic Scholar Open Data
   Training plan: Archive is a storage subsystem, not a standalone LoRA target at v0. Use checklist datasets to define schemas, indexing keys, and retrieval policies for future memory-conditioned agents.

20. Mystic-KnowledgeGraph - model `graph_db` - adapter `none`
   Division: Memory
   Implementation priority: 3
   Current stage: tool_only
   Checklist datasets: Wikipedia / Wikidata, Semantic Scholar Open Data, arXiv Metadata + Paper Subset, S2ORC
   Training plan: Build graph extraction and linking pipelines from structured academic and encyclopedic sources before any graph-aware adapter training.

21. Mystic-Evolution - model `dataset_builder` - adapter `none`
   Division: Memory
   Implementation priority: 3
   Current stage: tool_only
   Checklist datasets: Internal Mystic Data, PRM800K, Math-Shepherd Data, ToolBench, Open-SWE-Traces
   Training plan: Treat Evolution as the data curation layer that scores failures, promotes useful traces, and assembles new train-ready corpora from internal logs and external supervision sets.

22. Mystic-Report - model `qwen3-14b` - adapter `none`
   Division: Report
   Implementation priority: 1
   Current stage: planning_only
   Checklist datasets: Internal Mystic Data, FLAN Collection, Tulu 3 Datasets, CoT Collection, Semantic Scholar Open Data, arXiv Metadata + Paper Subset, StackExchange Dumps
   Training plan: Train uncertainty-preserving report generation from archived findings, Raven critiques, and experiment summaries. Keep report synthesis separate from Core routing and Raven verification.

## Execution Note

- The current repository can run a real Raven training cycle through the Qwen 0.5B Kaggle path.
- Other agents are mapped here for data planning and manifest alignment, but most still need dedicated train-ready builders, configs, and higher-volume datasets before real training starts.

