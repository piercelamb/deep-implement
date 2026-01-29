# Vellum Prompt Execution Trace for VrmQuestionnaireSigClassificationCriteriaWorkflowV1

## Executive Summary

The `VrmQuestionnaireSigClassificationCriteriaWorkflowV1.run()` workflow executes **4 different Vellum prompts** through multiple child workflows and activities. Each question in the questionnaire triggers 1-3 prompt executions, and each question group triggers 1 prompt execution.

## Execution Flow

```
VrmQuestionnaireSigClassificationCriteriaWorkflowV1.run()
│
├─ Step 1: ParseBatchQuestionnairesWorkflowV1 (child workflow)
│   └─ NO VELLUM PROMPTS
│
├─ Step 2: _classify_questions_from_parsing_output()
│   └─ For each question → VrmQuestionClassificationWorkflowV1 (child workflow)
│       ├─ Prompt 1: classify_question_prompt_activity
│       │   └─ Calls: CLASSIFY_QUESTION_PROMPT
│       │
│       └─ Conditional (based on initial classification):
│           ├─ If partially matched:
│           │   └─ Prompt 2: classify_partially_matched_question_prompt_activity
│           │       └─ Calls: CLASSIFY_PARTIALLY_MATCHED_QUESTION_PROMPT
│           │
│           └─ If not partially matched:
│               └─ Prompt 3: question_bucket_classification_prompt_activity
│                   └─ Calls: QUESTION_BUCKET_CLASSIFICATION_PROMPT
│
├─ Step 3: group_questions()
│   └─ NO VELLUM PROMPTS (local grouping logic)
│
└─ Step 4: _create_criteria_for_question_groups()
    └─ For each question group → ProcessQuestionGroupCriteriaWorkflowV1 (child workflow)
        └─ Prompt 4: criteria_creation_prompt_activity
            └─ Calls: CRITERIA_CREATION_PROMPT
```

## Detailed Vellum Prompt Calls

### Prompt 1: CLASSIFY_QUESTION_PROMPT
**Location:** `ai_services/temporal_workers/activities/vellum/classify_question_prompt_activity.py:34`

**Called From:**
- Workflow: `VrmQuestionClassificationWorkflowV1.run()` (line 77)
- Parent Workflow: `VrmQuestionnaireSigClassificationCriteriaWorkflowV1._classify_questions_from_parsing_output()` (line 103)

**Purpose:** Initial classification of question to determine question type

**Input:**
- `question`: The question text to classify

**Output:**
- `question_type`: Type of the question

**Execution Pattern:** Called **once per question** in the questionnaire

---

### Prompt 2: CLASSIFY_PARTIALLY_MATCHED_QUESTION_PROMPT
**Location:** `ai_services/temporal_workers/activities/vellum/classify_partially_matched_question_prompt_activity.py:37`

**Called From:**
- Workflow: `VrmQuestionClassificationWorkflowV1.run()` (line 143)
- Parent Workflow: `VrmQuestionnaireSigClassificationCriteriaWorkflowV1._classify_questions_from_parsing_output()` (line 103)

**Purpose:** Classify questions that have partial matches in vector database

**Input:**
- `question`: The question text
- `similar_matches`: JSON array of similar matches from vector search

**Output:**
- `sig_classification`: SIG classification result

**Execution Pattern:** Called **conditionally** - only if question is classified as "partially matched" by Prompt 1

---

### Prompt 3: QUESTION_BUCKET_CLASSIFICATION_PROMPT
**Location:** `ai_services/temporal_workers/activities/vellum/question_bucket_classification_prompt_activity.py:35`

**Called From:**
- Workflow: `VrmQuestionClassificationWorkflowV1.run()` (line 164)
- Parent Workflow: `VrmQuestionnaireSigClassificationCriteriaWorkflowV1._classify_questions_from_parsing_output()` (line 103)

**Purpose:** Classify questions into SIG buckets when not partially matched

**Input:**
- `question`: The question text

**Output:**
- `sig_classification`: SIG classification result

**Execution Pattern:** Called **conditionally** - only if question is NOT classified as "partially matched" by Prompt 1

---

### Prompt 4: CRITERIA_CREATION_PROMPT
**Location:** `ai_services/temporal_workers/activities/vellum/criteria_creation_prompt_activity.py:33`

**Called From:**
- Workflow: `ProcessQuestionGroupCriteriaWorkflowV1.run()` (line 68)
- Parent Workflow: `VrmQuestionnaireSigClassificationCriteriaWorkflowV1._create_criteria_for_question_groups()` (line 131)

**Purpose:** Generate criteria/control baselines for a group of classified questions

**Input:**
- `grouped_controls`: Formatted text of grouped questions

**Output:**
- `ControlBaselineDTO`: Generated criteria with title, description, controls, etc.

**Execution Pattern:** Called **once per question group** after classification and grouping

---

## How to Find Each Prompt Call

### Method 1: Direct File Search
Search for the activity names in the codebase:
```bash
grep -r "classify_question_prompt_activity" ai_services/temporal_workers/
grep -r "classify_partially_matched_question_prompt_activity" ai_services/temporal_workers/
grep -r "question_bucket_classification_prompt_activity" ai_services/temporal_workers/
grep -r "criteria_creation_prompt_activity" ai_services/temporal_workers/
```

### Method 2: Search for vellum_execute_prompt
Find all places where `vellum_execute_prompt` is called:
```bash
grep -r "vellum_execute_prompt" ai_services/temporal_workers/activities/vellum/
```

This returns:
- `ai_services/temporal_workers/activities/vellum/question_bucket_classification_prompt_activity.py`
- `ai_services/temporal_workers/activities/vellum/classify_partially_matched_question_prompt_activity.py`
- `ai_services/temporal_workers/activities/vellum/classify_question_prompt_activity.py`
- `ai_services/temporal_workers/activities/vellum/criteria_creation_prompt_activity.py`

### Method 3: Trace Through Workflow Execution
1. Start at `VrmQuestionnaireSigClassificationCriteriaWorkflowV1.run()` in `questionnaire_sig_classification_criteria_workflow_v1.py`
2. Look for `workflow.execute_child_workflow()` and `workflow.start_child_workflow()` calls
3. Follow each child workflow to find activity executions via `workflow.execute_activity()`
4. Check each activity to see if it calls `vellum_execute_prompt()`

### Method 4: Use Temporal UI
When running the workflow in Temporal:
1. Open the workflow execution in Temporal UI
2. Look at the workflow history/events
3. Activity executions will show up with their names
4. Activities ending in `_prompt_activity` are likely Vellum prompt calls

## Execution Volumes

For a typical questionnaire with N questions:

**Classification Phase:**
- Prompt 1 (CLASSIFY_QUESTION): **N executions** (once per question)
- Prompt 2 or 3: **N executions** (one of these per question, based on classification)
- **Total for classification: 2N prompt executions**

**Criteria Creation Phase:**
- Prompt 4 (CRITERIA_CREATION): **M executions** (once per question group, where M is the number of groups)
- **Total for criteria creation: M prompt executions**

**Grand Total: 2N + M Vellum prompt executions**

## Cost/Performance Considerations

- Classification happens in parallel (all questions classified concurrently via child workflows)
- Criteria creation happens in parallel (all groups processed concurrently via child workflows)
- Each prompt execution is an activity with retries enabled
- Prompt 1 always executes, then conditionally either Prompt 2 OR Prompt 3 executes (never both)

## Related Files

**Workflows:**
- `ai_services/temporal_workers/workflows/vrm/questionnaire_sig_classification_criteria_workflow_v1.py`
- `ai_services/temporal_workers/workflows/vrm/vrm_question_classification_workflow_v1.py`
- `ai_services/temporal_workers/workflows/vrm/process_question_group_criteria_workflow_v1.py`
- `ai_services/temporal_workers/workflows/vrm/parse_batch_questionnaires_workflow_v1.py`

**Activities:**
- `ai_services/temporal_workers/activities/vellum/classify_question_prompt_activity.py`
- `ai_services/temporal_workers/activities/vellum/classify_partially_matched_question_prompt_activity.py`
- `ai_services/temporal_workers/activities/vellum/question_bucket_classification_prompt_activity.py`
- `ai_services/temporal_workers/activities/vellum/criteria_creation_prompt_activity.py`
- `ai_services/temporal_workers/activities/vellum/vellum_execute_prompt.py` (core function)

**Helper Functions:**
- `ai_services/temporal_workers/question_classification_grouping/sig_grouping.py:group_questions()`
- `ai_services/temporal_workers/workflows/utils.py:start_children_with_dedup()`
