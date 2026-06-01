"""
Seed script — uploads sample policy documents to AskPolicy via the API.
Usage: python scripts/seed_documents.py --api-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import asyncio
import httpx
from pathlib import Path


SAMPLE_POLICIES = [
    {
        "filename": "leave_policy.txt",
        "content": (
            "ANNUAL LEAVE POLICY\n\n"
            "All full-time employees are entitled to 20 days of paid annual leave per year.\n"
            "Part-time employees receive leave on a pro-rata basis.\n\n"
            "REQUESTING LEAVE\n"
            "Leave requests must be submitted via the HR portal at least 2 weeks in advance.\n"
            "Emergency leave may be approved by direct managers with 24-hour notice.\n\n"
            "CARRY-OVER POLICY\n"
            "Unused leave up to 5 days may be carried over to the following year.\n"
            "Carried-over leave expires on March 31st of the following year.\n"
        ),
        "metadata": {"document_name": "Annual Leave Policy", "department": "HR", "version": "2024-01"},
    },
    {
        "filename": "expense_policy.txt",
        "content": (
            "EXPENSE REIMBURSEMENT POLICY\n\n"
            "Employees may claim reimbursement for business-related expenses.\n\n"
            "MEAL ALLOWANCES\n"
            "Breakfast: up to $15. Lunch: up to $25. Dinner: up to $50.\n"
            "Alcohol is not reimbursable unless pre-approved by a VP.\n\n"
            "TRAVEL\n"
            "Economy class is standard for flights under 6 hours.\n"
            "Business class may be approved for flights over 6 hours with manager sign-off.\n"
            "Hotel stays: up to $250/night in major cities, $180/night elsewhere.\n\n"
            "CLAIMS PROCESS\n"
            "Submit expense reports within 30 days of incurring expenses.\n"
            "Receipts are required for all expenses over $25.\n"
        ),
        "metadata": {"document_name": "Expense Reimbursement Policy", "department": "Finance", "version": "2024-03"},
    },
]


async def seed(api_url: str) -> None:
    async with httpx.AsyncClient(base_url=api_url, timeout=60) as client:
        for policy in SAMPLE_POLICIES:
            print(f"Uploading: {policy['metadata']['document_name']} ...")
            meta = policy["metadata"]
            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": (policy["filename"], policy["content"].encode(), "text/plain")},
                data={
                    "document_name": meta.get("document_name", ""),
                    "version": meta.get("version", ""),
                    "department": meta.get("department", ""),
                },
            )
            if response.status_code in (200, 202):
                print(f"  OK  → {response.json()['document_id']}")
            elif response.status_code == 409:
                print(f"  SKIP → already exists")
            else:
                print(f"  FAIL → {response.status_code}: {response.text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(seed(args.api_url))
