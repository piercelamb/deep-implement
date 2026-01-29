# Follow-up Questionnaire Ingestion API Spec

Author: Pierce Lamb

Date: 01/26/2026

**Introduction**

We have a product called TPRM Agentic Assessment. This product attempts to automate vendor assessments using AI. It takes an organization’s questionnaires as input and converts them into "criteria" (to-be-assessed per vendor). Then when an assessment is created, the organization uploads the vendors security documents (policies, SOC2, etc) which are indexed into a VectorDB namespace and the criteria are assessed against the documents.

The output of each criterion is "MET/NOT_MET/INCONCLUSIVE". The user can review these outputs and when they see a NOT_MET or INCONCLUSIVE, maybe they want the vendor to clarify or respond to something about it.

The VRM agent *automatically* creates a follow up questionnaire combining all NOT_MET and INCONCLUSIVE criteria for the vendor to clarify. The user has the chance to modify these criteria before the follow up is sent.

The vendor receives the questionnaire, when the vendor "submits", these follow up questionnaire values are stored in the database.

If the user DID NOT modify the automatic follow up questionnaire, we automatically re-run the assessment on *just* the follow up questionnaire criteria.

If the user DID modify the automatic follow up questionnaire, we automatically re-run the assessment on *all* of the criteria (since we can't know how their modifications impact the entire assessment).

There is no limit on the number of follow-up questionnaires a user can send to a vendor throughout the course of a security review.

The data entered into the follow-up questionnaire is supposed to be given precedence over any other data in the security review during these re-assessments.

As such, we must index the follow-up questionnaire data into the same VectorDB namespace as the vendors documents to include them during RAG.

To this end, ai-services created a new API endpoint

## **/api/v1/vrm/followup-questionnaire/index invocation**

Endpoint: `/api/v1/vrm/followup-questionnaire/index`

Example invocation:

```json
 {
    "jobId": <uuid>,
    "tenantId": <uuid>,
    "tenantName": "Acme Corp",
    "assessmentId": <vendor-assessment-id>,
    "vendorId": <uuid>,
    "vendorName": "Example Vendor",
    "vendorDocumentIndexId": <TPRM-index-id-for-this-vendor>,
    "followupRound": 1,
    "formId": <form-id-of-the-followup-questionnaire>,
    "responses": [
      {
        "criterionQuestionText": "Does the vendor enforce MFA for all users?",
        "questionText": "Is MFA enforced for all users including admins?",
        "answerText": "Yes, MFA is enforced for all users including administrators.",
        "notes": null
      },
      {
        "questionText": "Provide your data retention policy.",
        "answerText": "We retain customer data for 30 days after contract termination unless legally required longer."
      }
    ],
    "submittedAt": "2026-01-26T18:30:00Z"
  }'
```

Critical parts of the invocation:

- `vendorDocumentIndexId` must be the same document index id that was used for this vendors security review.
- `assessmentId` the UUID of the vendor security review.
- `followupRound` this is the round of follow-up questionnaire the invocation represents. For e.g. if its the first follow-up questionnaire sent for this review, it should be `1`. If its the second, `2` etc.
- `formId` is the identifier for the follow-up questionnaire in the database
- `responses.criterionQuestionText` - A follow-up questionnaire is auto-generated from NOT_MET/INCONCLUSIVE criterion questions. This field is for the original criterion question. If the user *adds* a new question to the questionnaire, this field can be left off or `null`.
- `responses.questionText` - This is the exact text of the question asked, it could be identical to `criterionQuestionText` or the user could have modified it.
- `responses.answerText` - This is the answer the vendor provided.
    - In the case of a file upload, these questions should be filtered out of the API invocation (files uploaded should be processed by the `create_document` endpoint)
    - In the case of a single select or multi-select, the answer should be concatenated into a single string
- `responses.notes`
    - This is an added optional field because i wasn’t sure all the data the user would be entering into a follow-up questionnaire. If there is more than just `answer` it can go in this field.

Note

- The endpoint does not handle file-upload-based questions (these should be filtered before invoking) and that it will return a validation error if `responses.questionText` or `responses.answerText` are empty

## **/api/v1/vrm/followup-questionnaire/index response**

Like other AI-services endpoints, this endpoint immediately returns back the `jobId` `tenantId` and `tenantName` to the caller. **The caller should store the `jobId` to correlate incoming webhooks.**

It then asynchronously sends webhooks as things complete. The webhook interaction is isomorphic to the SOC2 summary endpoint. It parses the invocation, generates external ids for *all* of the follow-up responses its going to index, returns that batch of `pendingExternalIds` then fires off child processes to index each one of them.

### Understanding `pendingExternalIds`

- **What are they?** Each follow-up questionnaire response gets a unique external ID that identifies it in the VectorDB. These IDs are pre-generated by ai-services before indexing begins.
- **How are they constructed?** The format is: `{assessmentId}--FOLLOWUPQUESTIONNAIRE--{contentHash}--{followupRound}` where `contentHash` is a hash of the question+answer content.
- **One per question**: Each response in the `responses` array will have its own external ID.
- **Why do you need them?** These external IDs must be passed to the vendor assessment endpoint when re-running the assessment (see [Caller Responsibilities](#caller-responsibilities) below).

### Initial Webhook

The `pendingExternalIds` webhook is sent once the endpoint has processed the invocation and is preparing for indexing:

Path: `/ai-agent/vrm/webhook/followup-questionnaire`

Body:

```json
{
  "status": "SUCCESS",
  "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "tenantId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "vendorId": "a3bb189e-8bf9-4e0e-b1df-6c9a0c5b8f3a",
  "followupRound": 1,
  "totalCount": 3,
  "pendingExternalIds": [
    "b2c3d479-58cc-4372-a567-0e02b2c3d479--FOLLOWUPQUESTIONNAIRE--7fc59e31f47890bb--1",
    "b2c3d479-58cc-4372-a567-0e02b2c3d479--FOLLOWUPQUESTIONNAIRE--c85999031b6e3e38--1",
    "b2c3d479-58cc-4372-a567-0e02b2c3d479--FOLLOWUPQUESTIONNAIRE--12502a3291184aba--1"
  ]
}
```

This basically informs the caller: “You *should* receive 3 webhooks later, one for each of these externalIds”.

In the example scenario above the three later webhooks would look like:

Path: `/ai-agent/vrm/webhook/followup-questionnaire`
1: 

```json
{
"status": "SUCCESS",
"jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
"tenantId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
"vendorId": "a3bb189e-8bf9-4e0e-b1df-6c9a0c5b8f3a",
"roundNumber": 1,
"totalCount": 3,
"responseExternalId": "b2c3d479-58cc-4372-a567-0e02b2c3d479--FOLLOWUPQUESTIONNAIRE--12502a3291184aba--1"
}
```

2:

```json
{
  "status": "SUCCESS",
  "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "tenantId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "vendorId": "a3bb189e-8bf9-4e0e-b1df-6c9a0c5b8f3a",
  "roundNumber": 1,
  "totalCount": 3,
  "responseExternalId": "b2c3d479-58cc-4372-a567-0e02b2c3d479--FOLLOWUPQUESTIONNAIRE--c85999031b6e3e38--1"
}
```

3:

```json
{
  "status": "SUCCESS",
  "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "tenantId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "vendorId": "a3bb189e-8bf9-4e0e-b1df-6c9a0c5b8f3a",
  "roundNumber": 1,
  "totalCount": 3,
  "responseExternalId": "b2c3d479-58cc-4372-a567-0e02b2c3d479--FOLLOWUPQUESTIONNAIRE--7fc59e31f47890bb--1"
}
```

## Potential Caller Responsibilities

The caller (frontend/backend consuming this API) is responsible for:

1. **Store the `jobId`** from the initial API response to correlate incoming webhooks.

2. **Track `pendingExternalIds`** from the first webhook. This tells you how many per-response webhooks to expect.

3. **Handle per-response webhooks** as they arrive:
   - `SUCCESS`: Store the `responseExternalId` - you'll need it when re-running the assessment.
   - `FAILURE`: Handle the error appropriately (log, notify user, etc.)

4. **Pass successful externalIds when re-running the assessment**: The follow-up questionnaire externalIds with `SUCCESS` status must be included in the `documents` array when calling the vendor assessment endpoint. They go in the same field as regular document externalIds:

```javascript
request.data = JSON.stringify({
    // ... other fields ...
    vendorAssessmentData: {
        criteriaWithQuestions: criteriaChunk,
        documentIndexId,
        documents: [
            // existing vendor document externalIds
            ...existingDocumentIds,
            // ADD the successful follow-up questionnaire externalIds here
            ...successfulFollowupExternalIds
        ],
        vendorId: securityReview.vendor.id,
        vendorName: securityReview.vendor.name,
        securityReviewId: securityReview.id,
    },
});
```

This ensures the follow-up questionnaire data is included in RAG retrieval during re-assessment, giving it the opportunity to influence (and potentially change) criterion outcomes.