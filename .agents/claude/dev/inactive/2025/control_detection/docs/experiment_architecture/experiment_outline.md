# Control Ranking and Grouping

How do we reduce the space of candidate controls from potentially 1000s to 500 or less?

- Loads a PDF and splits it into page images  
- Loads a ground truth set mapping those PDFs to human-verified controls  
- Loads a set of control candidates to map to each PDF  
- If K-Means clusters for the controls have not been computed, they are computed.  
  - We set n\_clusters to 50 to match the number of LLM batches we'll later have.  
  - The embeddings for each control are extracted from ColModernVBERT and used to cluster  
  - This creates groups of semantically similar controls.  
  - Clustering is thoroughly explained here: @.agents/claude/dev/active/control\_detection/docs/clustering\_explained.md  
- Run each page and the entire set of control candidates through ColModernVBERT  
  - This returns a ranking score for each control, ranked against the page image  
- The controls are thresholded based on their score. Anything below 0.48 is filtered out  
  - A key change we made here was flipping the scoring from PAGE\_COVERAGE to CONTROL\_COVERAGE and normalizing scores. See the doc below.  
  - ColModernVBERT usage and scoring more thoroughly explained here: @.agents/claude/dev/active/control\_detection/planning/research/low\_vbert\_threshold/colmodernvbert\_score\_normalization.md  
- The controls that survive are deduplicated.  
- The deduplicated controls then go through a tiered grouping strategy.  
  - First, they are then grouped by page.  
  - The hope here is that the LLM that analyzes them can get controls whose evidence is on similar pages  
- If one of these groupings is greater than size 10 we:  
  - Load the k-means clusters from earlier.  
  - Attempt to intelligently break up the large cluster using the k-means clusters as a lever  
  - The hope here is that if they cant be grouped by page, if they're grouped by similarity, then the evidence founding them is probably on the same page.  
- After we've completed tiered grouping, if our groups don't fully saturate the available LLM calls (50 calls, 10 controls per), we expand them to fill all 50 slots by removing controls from size 10 batches.  
  - This ensures less context to manage if we have the open slots  
  - In production we probably wouldn’t do this.  
- If our groups are greater than our available slots (all 50 saturated with groups greater than 10\) we drop controls by their ColModernVBERT score  
- This is explained more thoroughly here: @.agents/claude/dev/active/control\_detection/planning/tiered\_grouping/plan.md


**Why ColModernVBERT**? Its a multi-vector image/text reranker that can run on CPU in an AWS lambda

# Teaching the LLM to Map

We've learned time and again that "Does control X map to document Y?" is not a good strategy. Control mapping is a far more nuanced task than that. I developed a plan for reverse engineering ground truths and false negative/false positive analysis back into coherent instructions for the LLM to follow

We have 100s of ground truths (and, after runs of the experiment) false negative and false positive predictions across \~40 policy documents. How can we learn from this data?

Use the most intelligent model available because this is a 1 time task.

For each policy:

- Load the policy into the context cache  
- For each GT, FN or FP  
- Send a prompt that amounts to:  
- Why is this a GT, FN or FP?  
  - constraining the reasoning above beforehand helps a lot (e.g. classifications of why), but its not necessary.  
- LLM emits reasoning about why its a GT, FN or FP  
- A second prompt iterates these reasons and attempts to convert them into "rules" or "decision rules" \-- basically take the reasoning and generate a rule that enforces it that is generalizable (not specific to this exact GT/FN or FP, but based on it).  
- Once we have this first layer of rules, we run a MapReduce style flow:  
  - For any two sets of these rules combine similar rules and keep unique rules unique  
  - Continue doing rounds of this until we have one single set of universal rules and one single set of unique rules  
- Ask another LLM to take the current prompt and the outputted set of universal and rare rules and incorporate them as instructions into the current prompt  
- The above feature was planned and replanned here (the dir contains logs of runs): @.agents/claude/dev/active/control\_detection/planning/map\_reduce  
- It was replanned in a number of places as i added FP and FN analysis to it

# The control mapping step

We have our batched/grouped controls and our prompt created from analyzing GT's FNs and FPs. Now we:

- Load the system prompt (which teaches the LLM how to map) and policy PDF into the context cache  
- For each control batch run the mapping prompt  
- Write outputs, calculate eval metrics  
- This was originally planned here: @.agents/claude/dev/active/control\_detection/planning/cached\_doc\_approach/implementation\_plan.md  
- The prompt(s) went through tons of prompt engineering. @.agents/claude/dev/active/control\_detection/planning/1000\_ft\_prompt\_refactor contains the most recent versions (full and distilled). @ai\_services/scripts/experiments/control\_detection/prompts/control\_centric\_plamb\_distilled

# The False Positive annihilation step

We eventually hit what felt like a local maxima on the above approach. Recall remained high around 80-90% but precision was very low (like 30%) due to so many false positives. It did not feel like any amount of prompt tweaking was going to make up a \~50% gap in precision (product was requiring an 80% f1 score).

Additionally, we had hard latency constraints around this feature. The first prediction should arrive no later than 30s; that severely limits what we can do. Our existing two stage architecture worked like this:

Stage 1: Rank controls against document and create batches for processing   
Stage 2: Load document into context cache and run batches

In a desperate attempt to increase precision I needed a way to add a Stage 3 that was very fast. From Stage 2, we already had the entire policy and the instructions for mapping in the context cache. Having all this context cached makes subsequent LLM calls against it quite fast and cheap. I decided to try adding a 3rd step where the prompt would get the same context cache as Stage 2, but it would have a new user prompt that operated on ONLY the MAPPED outputs from stage 2 and only 1 at a time. The idea was to treat Stage 2 basically like a reranking step, knowing that most of its MAPPED outputs are false positives, then have a more targeted user prompt and less control context for the LLM to deal with and hope that this increased precision.

In terms of latency, the thought was that while all these "batches" of Stage 2 controls were in a queue or something being processed, if any emitted `MAPPED` a Stage 3 request would enter that queue and immediately get priority so that very little latency was added to time-to-first-prediction.

This was planned in @.agents/claude/dev/active/control\_detection/planning/three\_stage\_mapping/plan.md and implemented, but very little experimentation has occurred against it. It can be run independently of the other stages via @ai\_services/scripts/experiments/control\_detection/run\_stage3\_standalone.py

# Additional notes:

All experiments are tracked here: @.agents/claude/dev/active/control\_detection/results

I left off running my extremely distilled prompt against stage 2 (the standard experiment): @ai\_services/scripts/experiments/control\_detection/prompts/control\_centric\_plamb\_distilled

It'd be nice to refactor the stage 3 prompt given this distilled system prompt and see how stage 3 performs against the above outputs

This is where the last experiment left off:

\======================================================================  
EXPERIMENT RESULTS  
\======================================================================  
Documents evaluated: 37

Retrieval Stage (before LLM):  
  Embedding recall: 98.3% (575/585 GT controls pass threshold)  
  Sent to LLM:      96.9% (567/585 GT controls in LLM batches)  
  GT lost at threshold: 10  
  GT not in batches:  8

Counts:  
  Ground truth controls: 585  
  Predicted controls:    957  
  True positives:        385  
  False positives:       572  
  False negatives:       200

Micro-averaged (pooled across all docs):  
  Precision: 40.2%  
  Recall:    65.8%  
  F1:        49.9%

Macro-averaged (mean of per-doc metrics):  
  Precision: 39.2%  
  Recall:    67.3%  
  F1:        43.7%

Time to First MAPPED:  
  Documents with MAPPED: 37/37  
  Mean:   27.26s  
  Median: 21.28s  
  Min:    7.82s  
  Max:    91.49s

MAPPED Predictions (Stage 3 call projection):  
  Total MAPPED:  957  
  Mean per doc:  25.9  
  Median:        20.0  
  Min:           3  
  Max:           193  
\======================================================================

| Document                               |   P% |    R% |  F1% | Pred |  GT |  TP |  FP |  FN | Issue Pattern        |  
  |----------------------------------------|------|-------|------|------|-----|-----|-----|-----|----------------------|  
  | Breach Notification Policy             |  0.0 |   0.0 |  0.0 |   11 |   1 |   0 |  11 |   1 | All wrong            |  
  | Privacy, Use, and Disclosure Policy    |  5.6 | 100.0 | 10.5 |   36 |   2 |   2 |  34 |   0 | Massive over-mapping |  
  | Business Associate Policy              |  8.3 | 100.0 | 15.4 |   12 |   1 |   1 |  11 |   0 | Massive over-mapping |  
  | Code of Conduct                        | 14.3 |  33.3 | 20.0 |    7 |   3 |   1 |   6 |   2 | Over-mapping         |  
  | Data Classification Policy             | 14.3 |  33.3 | 20.0 |   14 |   6 |   2 |  12 |   4 | Over-mapping         |  
  | Information Governance Policy          | 12.5 | 100.0 | 22.2 |    8 |   1 |   1 |   7 |   0 | Massive over-mapping |  
  | Disaster Recovery Plan                 | 20.0 |  33.3 | 25.0 |    5 |   3 |   1 |   4 |   2 | Over-mapping         |  
  | Personal Data Management Policy        | 14.8 |  80.0 | 25.0 |   27 |   5 |   4 |  23 |   1 | Massive over-mapping |  
  | Shared Responsibility Policy           | 14.3 | 100.0 | 25.0 |   14 |   2 |   2 |  12 |   0 | Massive over-mapping |  
  | Public Cloud PII Protection Policy     | 20.0 |  50.0 | 28.6 |   20 |   8 |   4 |  16 |   4 | Over-mapping         |  
  | Data Protection Policy                 | 24.4 |  39.3 | 30.1 |   45 |  28 |  11 |  34 |  17 | Both problems        |  
  | Risk Assessment Policy                 | 66.7 |  25.0 | 36.4 |    6 |  16 |   4 |   2 |  12 | Under-mapping        |  
  | ISMS \+ PIMS Plan                       | 23.3 |  93.3 | 37.3 |   60 |  15 |  14 |  46 |   1 | Massive over-mapping |  
  | AIMS Plan                              | 30.0 |  71.4 | 42.3 |   50 |  21 |  15 |  35 |   6 | Over-mapping         |  
  | Encryption Policy                      | 43.8 |  46.7 | 45.2 |   16 |  15 |   7 |   9 |   8 | Both problems        |  
  | Information Security Policy            | 50.0 |  46.9 | 48.4 |   30 |  32 |  15 |  15 |  17 | Both problems        |  
  | ISMS Plan 2022                         | 34.8 |  94.1 | 50.8 |   46 |  17 |  16 |  30 |   1 | Over-mapping         |  
  | Logging and Monitoring Policy          | 51.5 |  51.5 | 51.5 |   33 |  33 |  17 |  16 |  16 | Both problems        |  
  | Password Policy                        | 46.2 |  60.0 | 52.2 |   13 |  10 |   6 |   7 |   4 | Mild over-mapping    |  
  | Software Development Life Cycle Policy | 47.6 |  58.8 | 52.6 |   21 |  17 |  10 |  11 |   7 | Mild over-mapping    |  
  | Business Continuity Plan               | 44.4 |  66.7 | 53.3 |    9 |   6 |   4 |   5 |   2 | Mild over-mapping    |  
  | Change Management Policy               | 50.0 |  57.9 | 53.7 |   22 |  19 |  11 |  11 |   8 | Both problems        |  
  | Vulnerability Management Policy        | 71.4 |  50.0 | 58.8 |   14 |  20 |  10 |   4 |  10 | Under-mapping        |  
  | Backup Policy                          | 60.0 |  60.0 | 60.0 |    5 |   5 |   3 |   2 |   2 | Balanced             |  
  | Vendor Management Policy               | 54.5 |  80.0 | 64.9 |   22 |  15 |  12 |  10 |   3 | Mild over-mapping    |  
  | Physical Security Policy               | 80.0 |  59.3 | 68.1 |   20 |  27 |  16 |   4 |  11 | Under-mapping        |  
  | Incident Response Plan                 | 66.7 |  70.0 | 68.3 |   21 |  20 |  14 |   7 |   6 | Good                 |  
  | Data Retention Policy                  | 58.3 |  87.5 | 70.0 |   12 |   8 |   7 |   5 |   1 | Good                 |  
  | PCI DSS Compliance Policy              | 62.2 |  81.1 | 70.4 |  193 | 148 | 120 |  73 |  28 | Good (high volume)   |  
  | Network Security Policy                | 76.5 |  68.4 | 72.2 |   17 |  19 |  13 |   4 |   6 | Good                 |  
  | Maintenance Management Policy          | 85.7 |  75.0 | 80.0 |    7 |   8 |   6 |   1 |   2 | Best                 |  
  | System Security Planning Policy        | 66.7 | 100.0 | 80.0 |    3 |   2 |   2 |   1 |   0 | Best                 |  
