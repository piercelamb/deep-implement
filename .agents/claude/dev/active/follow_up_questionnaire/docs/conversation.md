Vadillo
  11:45 AM
@piercelamb that endpoint will re-run the assessment?
11:45
or we should re-run the assessment after consume that endpoint? (edited) 
piercelamb
  11:46 AM
re-run it after you consume that endpoint. That endpoint basically tells you "okay the follow-up questionnaire's data is indexed and ready to be run against"
Vadillo
  11:49 AM
perfect thx
Vadillo
  11:57 AM
pierce what is the ETA to merge it?
piercelamb
  12:09 PM
should be soon, its been sitting in review for like a week
12:09
just waiting on JJ to review it
Vadillo
  12:11 PM
oko
Vadillo
  9:38 AM
Hi Pierce, I was reading the Notion doc for followup-questionnaire/index yesterday and I have a few questions:
Do we need to store anything on our side from the response in order to know how to process what will be sent in the webhook?
What are pendingExternalIds? How is that ID constructed? Is it per question?
piercelamb
  9:50 AM
the initial response returns the jobId which you may need to track?
the ai-services side pre-constructs the external ids of each followup questionnaire question before it indexes them. pendingExternalIds informs the caller of all these external ids.
(note here that the endpoint does not handle file-upload-based questions (these should be filtered before invoking) and that it will return a validation error if responses.questionText or responses.answerText are empty)
ai-services then kicks off n children processes for each external id to do the actual indexing. The last step of each of these children processes is sending a webhook for its given externalId about the success or failure of indexing that external_id
so the burden on the caller is this:
Understanding which externalIds it should expect to receive a webhook for (from pendingExternalIds)
Handling those webhooks based on SUCCESS or FAILURE
when the assessment is re-run, passing the externalIds with SUCCESS to the vendor assessment call (along with its normal document ids)
@zach is implementing bookkeeping for this webhook style (pendingExternalIds -> singular webhooks) as we speak for SOC2 Summary (it follows the same model) so it might be worth syncing with him in case there are reusable abstractions
Vadillo
  11:30 AM
when the assessment is re-run, passing the externalIds with SUCCESS to the vendor assessment call (along with its normal document ids)
We need to send the followup externalIds  in vendorAssessmentData in a new field?
request.data = JSON.stringify({
                    workflowId: workflow.id,
                    stepId: step.id,
                    productId: '123e4567-e89b-12d3-a456-426614174010',
                    productName: 'Acme Payroll',
                    tenantId: account.id,
                    tenantName: account.companyName,
                    vendorAssessmentData: {
                        criteriaWithQuestions: criteriaChunk,
                        documentIndexId,
                        documents,
                        vendorId: securityReview.vendor.id,
                        vendorName: securityReview.vendor.name,
                        securityReviewId: securityReview.id,
                    },
                });
piercelamb
  11:31 AM
i imagine that documents contains a list of externalIds of the documents in the vendor document index. The externalIds returned by followup-questionnaire/index need to be added to this list (when the assessment its re-run)