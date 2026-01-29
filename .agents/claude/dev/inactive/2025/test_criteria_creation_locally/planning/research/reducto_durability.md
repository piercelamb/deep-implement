Here's the summary of the Reducto timeout/failure handling:

  Key Findings

  Timeouts

  | Level                 | Timeout    | Notes                               |
  |-----------------------|------------|-------------------------------------|
  | Per activity call     | 3 minutes  | Each Reducto API call               |
  | Per document workflow | 1 hour     | ParseSingleQuestionnaireWorkflowV1  |
  | Polling interval      | 10 seconds | Between status checks               |
  | Max poll attempts     | None!      | Polls forever until success/failure |

  The Problem: No Max Poll Attempts

  In parse_single_questionnaire_workflow_v1.py:120-150:

  async def _await_completion(self, reducto_job_id: str, activity_kwargs: dict) -> dict[str, Any]:
      job_completed = False
      attempt = 1

      while job_completed is False:  # <-- INFINITE LOOP
          job_output = await workflow.execute_activity(...)

          if job_output.status == COMPLETED:
              return job_output.result.data
          elif job_output.status == FAILED:
              raise ApplicationError(...)

          attempt += 1
          await workflow.sleep(10)  # Wait 10 seconds

      raise ApplicationError("Max polling attempts reached...")  # <-- UNREACHABLE CODE

  The loop never exits unless Reducto returns COMPLETED or FAILED. If Reducto returns Pending forever (or some other status), the
  workflow polls indefinitely until the 1-hour timeout.

  Failure Webhooks

  - Parsing workflows do NOT send failure webhooks
  - Only the parent VrmQuestionnaireSigClassificationCriteriaWorkflowV1 sends a CRITERIA_CREATION_ERROR webhook
  - Partial failures (some docs succeed, some fail) don't trigger error webhooks - the batch continues

  Retry Policy

  - 3 attempts with exponential backoff (5s, 10s)
  - Non-retryable: 4xx errors (except 429), Reducto FAILED status

  ---
  Recommendations

  1. Add max polling attempts - The config already has vellum_document_status_polling_maximum_attempts: int = 10 but nothing similar for
  Reducto
  2. Use the existing pattern - Look at how Vellum document polling handles this (it likely has a max attempts)
  3. Make the unreachable code reachable - Add a max attempts check to actually exit the loop

  Would you like me to implement a fix to add max polling attempts to the Reducto polling logic?