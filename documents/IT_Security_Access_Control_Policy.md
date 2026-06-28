# IT Security and Access Control Policy

Document ID: IT-POL-002
Effective date: 2026-02-01
Owner: Information Security
Applies to: Employees, contractors, interns, and temporary workers

## 1. Purpose

This policy defines requirements for account access, passwords, multifactor authentication, device security, data handling, and incident reporting. It is fictional content for chatbot testing.

## 2. Account Provisioning

Access to company systems must be requested through the service desk ticketing system. Each request must include the business justification, system name, role requested, manager approval, and expected duration if the access is temporary.

Standard access for new employees is provisioned based on job role. Privileged access requires separate approval from the system owner and Information Security.

Shared user accounts are prohibited unless Information Security grants a written exception for a system that cannot technically support named accounts.

## 3. Password Requirements

Passwords must be at least 14 characters long. Passwords must not include the employee's name, company name, product name, birth date, or common keyboard patterns.

Passwords must not be reused across company and personal services. Password managers approved by IT may be used to store credentials.

Password rotation is required only when compromise is suspected, an employee changes privileged role, or a system-specific regulation requires rotation.

## 4. Multifactor Authentication

Multifactor authentication is required for email, source code repositories, cloud infrastructure, finance systems, HR systems, VPN, and any system containing confidential or restricted data.

Push-based MFA fatigue must be reported as a suspected security incident. Employees must not approve MFA prompts they did not initiate.

## 5. Device Security

Company-managed laptops must use full disk encryption, automatic screen lock after 10 minutes of inactivity, endpoint protection, and supported operating system versions.

Personal devices may access email and calendar only if mobile device management controls are enabled. Personal devices must not store restricted company data locally.

Lost or stolen devices must be reported to the service desk and Information Security within 1 hour of discovery.

## 6. Access Reviews

Managers must review team access quarterly. System owners must review privileged access monthly.

Access must be removed within 24 hours when an employee changes roles and the access is no longer required. Access must be removed immediately when employment ends for cause.

## 7. Data Classification

Public data may be shared externally without approval.

Internal data may be shared with employees and approved contractors.

Confidential data may be shared only with people who have a business need to know.

Restricted data includes passwords, private keys, government IDs, health information, payment card data, and customer secrets. Restricted data must be encrypted in transit and at rest.

## 8. Incident Reporting

Employees must report suspected phishing, malware, unauthorized access, accidental data exposure, or lost devices immediately.

Security incidents should be reported to security@example.test. Urgent incidents may also be reported by phone to the 24-hour security hotline listed on the intranet.

Do not delete suspicious emails, logs, or files unless Information Security instructs you to do so.

## 9. Exceptions

Policy exceptions must have a business justification, compensating control, named owner, and expiration date. Exceptions longer than 90 days require approval from the Chief Information Security Officer.

## 10. Examples

Example 1: A contractor needs temporary access to a repository for 2 weeks. The manager must submit a ticket with business justification and end date.

Example 2: An employee receives 12 MFA prompts they did not initiate. The employee must deny the prompts and report the activity as a suspected incident.

Example 3: A system cannot support individual accounts. The system owner must request a shared-account exception and define monitoring controls.
