Ramen Recommendation LINE Bot
This project is a LINE Messaging API bot that recommends ramen restaurants based on user queries.
It uses natural language processing, location extraction, and FAISS vector search to provide relevant results with ratings, photos, and Google Maps links.

Features
Location-aware search: Extracts location names from user queries and prioritizes nearby stores

Ramen store recommendations: Uses FAISS similarity search to find matching restaurants from a dataset

Google Places API integration: Fetches photos, ratings, and reviews count

LINE Flex Messages: Displays rich cards with store name, rating (stars), photo, address, features, and map button

Multi-language support: Translates results based on user language

FastAPI backend: Handles LINE webhook requests

Tech Stack
Python

FastAPI – Web API framework for LINE webhook

LangChain – NLP and document retrieval

FAISS – Vector similarity search

Google Places API – Location, photos, ratings

Geopy – Geocoding & distance calculation

LINE Messaging API – Sending messages & Flex templates

Docker – Containerized deployment

PostgreSQL (optional) – Data storage

Pydantic – Data validation

How It Works
User sends a ramen-related message to the LINE bot

Bot extracts location keywords (if any)

Searches FAISS vector store for similar restaurants

Ranks by distance if location is available

Fetches additional info from Google Places API

Returns top 3 results as Flex Messages
