#!/usr/bin/env python3
"""Script to test organization functionality."""

import argparse
import asyncio
import json

import httpx


async def list_organizations():
    """List all organizations."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/v1/organizations/")
        if response.status_code == 200:
            org_data = response.json()
            for org in org_data:
                print(
                    f"ID: {org['id']}, Name: {org['name']}, Email: {org['webhook_email']}, Active: {org['is_active']}"
                )
        else:
            print(
                f"Failed to list organizations: {response.status_code} - {response.text}"
            )
        return response.json() if response.status_code == 200 else None


async def get_organization(org_id: int):
    """Get an organization by ID."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/v1/organizations/{org_id}")
        if response.status_code == 200:
            org = response.json()
            print(
                f"ID: {org['id']}, Name: {org['name']}, Email: {org['webhook_email']}, Active: {org['is_active']}"
            )
        else:
            print(
                f"Failed to get organization: {response.status_code} - {response.text}"
            )
        return response.json() if response.status_code == 200 else None


async def create_organization(name: str, email: str, api_key: str, secret: str):
    """Create a new organization."""
    data = {
        "name": name,
        "webhook_email": email,
        "mandrill_api_key": api_key,
        "mandrill_webhook_secret": secret,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/organizations/",
            json=data,
        )
        if response.status_code == 201:
            org = response.json()
            print(
                f"Created organization - ID: {org['id']}, Name: {org['name']}, Email: {org['webhook_email']}"
            )
        else:
            print(
                f"Failed to create organization: {response.status_code} - {response.text}"
            )
        return response.json() if response.status_code == 201 else None


async def update_organization(
    org_id: int,
    name: str = None,
    email: str = None,
    api_key: str = None,
    secret: str = None,
    is_active: bool = None,
):
    """Update an organization."""
    data = {}
    if name is not None:
        data["name"] = name
    if email is not None:
        data["webhook_email"] = email
    if api_key is not None:
        data["mandrill_api_key"] = api_key
    if secret is not None:
        data["mandrill_webhook_secret"] = secret
    if is_active is not None:
        data["is_active"] = is_active

    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"http://localhost:8000/v1/organizations/{org_id}",
            json=data,
        )
        if response.status_code == 200:
            org = response.json()
            print(
                f"Updated organization - ID: {org['id']}, Name: {org['name']}, Email: {org['webhook_email']}"
            )
        else:
            print(
                f"Failed to update organization: {response.status_code} - {response.text}"
            )
        return response.json() if response.status_code == 200 else None


async def delete_organization(org_id: int):
    """Delete an organization."""
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"http://localhost:8000/v1/organizations/{org_id}"
        )
        if response.status_code == 204:
            print(f"Organization with ID {org_id} deleted successfully")
            return True
        else:
            print(
                f"Failed to delete organization: {response.status_code} - {response.text}"
            )
            return False


async def main():
    """Run the script."""
    parser = argparse.ArgumentParser(description="Test organization functionality")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    subparsers.add_parser("list", help="List all organizations")

    # get command
    get_parser = subparsers.add_parser("get", help="Get an organization by ID")
    get_parser.add_argument("id", type=int, help="Organization ID")

    # create command
    create_parser = subparsers.add_parser("create", help="Create a new organization")
    create_parser.add_argument("name", help="Organization name")
    create_parser.add_argument("email", help="Webhook email")
    create_parser.add_argument("api_key", help="Mandrill API key")
    create_parser.add_argument("secret", help="Mandrill webhook secret")

    # update command
    update_parser = subparsers.add_parser("update", help="Update an organization")
    update_parser.add_argument("id", type=int, help="Organization ID")
    update_parser.add_argument("--name", help="Organization name")
    update_parser.add_argument("--email", help="Webhook email")
    update_parser.add_argument("--api_key", help="Mandrill API key")
    update_parser.add_argument("--secret", help="Mandrill webhook secret")
    update_parser.add_argument("--active", type=bool, help="Is active")

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an organization")
    delete_parser.add_argument("id", type=int, help="Organization ID")

    args = parser.parse_args()

    if args.command == "list":
        await list_organizations()
    elif args.command == "get":
        await get_organization(args.id)
    elif args.command == "create":
        await create_organization(args.name, args.email, args.api_key, args.secret)
    elif args.command == "update":
        await update_organization(
            args.id, args.name, args.email, args.api_key, args.secret, args.active
        )
    elif args.command == "delete":
        await delete_organization(args.id)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
