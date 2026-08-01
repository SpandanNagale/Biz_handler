"""Vercel serverless entrypoint. Vercel's Python runtime looks for a WSGI `app`
object in this file; the actual application lives in the app/ package factory."""

from app import create_app

app = create_app()
