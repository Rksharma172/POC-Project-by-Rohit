# AI Usage and Chatbot Testing Policy

Document ID: AI-POL-007
Effective date: 2026-06-01
Owner: AI Governance Committee
Applies to: Employees and contractors using AI tools or testing AI-enabled applications

## 1. Purpose

This policy defines acceptable AI use, prohibited data inputs, review requirements, chatbot testing rules, evaluation records, and escalation paths. It is fictional content created specifically for chatbot testing.

## 2. Approved AI Use Cases

Employees may use approved AI tools to draft internal summaries, brainstorm ideas, classify non-sensitive content, generate sample test data, review code snippets without secrets, and create first drafts of internal communications.

AI output must be reviewed by a human before it is used for business decisions, customer communication, legal advice, financial advice, employment decisions, or security actions.

## 3. Prohibited Inputs

Employees must not enter restricted data into public or unapproved AI tools.

Restricted data includes passwords, access tokens, private keys, customer secrets, unpublished financial results, health information, government IDs, payment card data, confidential customer files, and legal privileged information.

Personal data may be used in approved AI systems only when the use case has been reviewed by the Privacy Office.

## 4. Chatbot Testing Content

Teams may create fictional policy documents, synthetic user questions, synthetic employee names, fake customer names, and simulated incident scenarios for chatbot testing.

Testing content must be clearly marked as fictional when stored outside a dedicated test environment.

Test data must not include real employee medical details, real customer contracts, real access credentials, or real confidential incident reports.

## 5. Evaluation Requirements

Before an AI chatbot is used with employees or customers, the project owner must test:

- Answer relevance
- Citation or source grounding
- Refusal behavior when documents do not contain the answer
- Handling of conflicting policies
- Handling of old policy versions
- Privacy and security boundaries
- Bias and harassment-related safety behavior
- Escalation to human support

The project owner must keep evaluation records for at least 18 months.

## 6. Source Grounding

Chatbots that answer policy questions must answer only from approved source documents. If the answer is not in the source documents, the chatbot should say that it does not know based on the provided documents.

Chatbots should identify the relevant source document when possible. They should not invent policy numbers, approval names, deadlines, or exceptions.

## 7. Human Review

Human review is required before using AI output for:

- Termination, promotion, compensation, or hiring decisions
- Legal notices or contract interpretation
- Security incident containment
- Regulatory filings
- Public financial statements
- Medical or benefits eligibility decisions

## 8. Incident Escalation

AI incidents must be reported to ai-governance@example.test and security@example.test when they involve data leakage, harmful output, unauthorized system access, repeated hallucination in production, or use of restricted data in an unapproved tool.

Critical incidents must be reported within 1 hour of discovery. Non-critical incidents must be reported within 2 business days.

## 9. Model and Vendor Approval

New AI vendors must complete procurement, security, privacy, and legal review before use.

High-risk AI systems require approval from the AI Governance Committee before launch. High-risk systems include systems used for employment decisions, credit decisions, legal recommendations, healthcare recommendations, or automated security enforcement.

## 10. Examples

Example 1: A developer uses fake employee names and fictional leave balances to test chatbot answers. This is allowed if the test data is clearly synthetic.

Example 2: A support manager pastes a real customer contract into an unapproved public AI tool for summarization. This is prohibited.

Example 3: A chatbot cannot find a policy about pet insurance. It should state that it does not know based on the provided documents instead of guessing.
