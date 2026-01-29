We need to document the journey so far:

* Reducing the space of controls  
* Experimenting in colmodernvbert  
  * Normalizing the scores  
  * CONTROL\_COVERAGE vs PAGE\_COVERAGE  
  * Trying to find a threshold that has 100% recall and filters pages  
  * accepting 90% recall and no filtered pages  
* Creating instructions for mapping policies to controls  
  * Using documents and ground truths to create reasons  
  * Using a MapReduce flow to turns reasons into general and rare rules  
  * Distilling those rules into instructions  
  * Distilling those instructions futher into LLM instructions  
* Two approaches to LLM decisions:  
  * Prompt-per page with neighboring pages  
    * Report recall/prevision accuary and latency  
  * Entire document in context cache  
    * Report recall/prevision accuary and latency  
* Created an entire detailed plan around clustering/batching up controls together. Controls now:  
  * get scored by colmodernvbert and thresholded/deduped  
  * get batched by page number (so llm can look at pages together)  
  * if a batch exceeds our allowed batch size:  
    * We retrieve pre-computed k-means clusters (based on colmodernvbert embeddings) of the controls  
    * We use those to try and keep similar controls together while breaking the large batches and filling slots in smaller batches  
  * For the experiment, we expand to fill all LLM slots (but we wouldnt do this in production)  
* Added a LLM-as-judge flow because many of the false negative ground truths seemed odd/repetitive. My suspicion was that many DCFs have changed since the GT was created that are mapped to policies. In essence some mappings were “stale”.  
  * This ran in the context of an experiment and “validated” the false negative ground truths into two buckets: GT\_WRONG and LLM\_WRONG  
  * After getting something like 84 GT\_WRONG’s, instead of asking the GRC team to fix, I simply filtered all of these out of the mappings  
  * This made recall jump nearly 20%  
* Now, we also had the bucket of LLM\_WRONGs to fix. I modified the MapReduce flow from earlier so it could do false negative analysis on this and generate universal and rare rules as a result of these.  
* We completed the LLM\_WRONG analysis implementation into the main prompt and ran experiment 5\. Recall jumped to 94% but precision went way down (as expected)  
* Now we are doing an analysis of false positives to try and strike a balance between recall and precision  
* Completed the false positive analysis (using a different method than MapReduce because there were so many, we grouped them by root cause first). Incorporated the universal rules and rare rules into the prompt  
* Precision still wasnt great, did two more rounds of false positive analysis (just from claude analyzing the outputs of a single doc). Lots of prompt tweaks.  
  * Got precision to jump 10ish percentage points, but still abysmal overall  
* Realized that we’d hit the local maxima of this approach in terms of recall/precision. Likely culprit is that flash is overwhelmed with context  
* Because we have the context cache with the mapping instructions and doc ready to go, came up with a “third stage” approach where we ask flash (using the same cache, but wiht a new user prompt and response schema) to “verify” single MAPPED controls  
* While we were implementing the above, we were also running a current experiment (experiment 6\) – this was an experiment meant to drastically limit false positives via prompt tweaking. After we’d implemented stage 3, it came back with much higher precision numbers but much lower recall numbers.  
  * This made stage 3 less interesting because its whole point is to take high recall output from stage 2 and boost the precision  
* As such, we did two rounds of false negative analysis and re-running the entire experiment. These resulted in a lot of prompt tweaks to try and boost recall back up from stage 2 (without losing too much precision) before we test stage 3  
* We tested stage 3, it did not perform nearly as well as we’d hoped.  
* We went back to the drawing board and re-wrote the system prompt instructions

