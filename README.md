====Restaurants Recommendation LINE Bot====
==================================================================================================================================================

A LINE Messaging API bot that recommends restaurants based on user queries.
It uses natural language processing, location extraction, and FAISS vector search to provide results with ratings, photos, and Google Maps links.

| 中文 | 日本語 | English |
|--------|------|---------|
| ![](images/zh.png) | ![](images/jp.png) | ![](images/en.png) |

★ Tech Stack★ 
==================================================================================================================================================

・ Python

・ FastAPI – Web API framework for LINE webhook

・ LangChain – NLP and document retrieval

・ FAISS – Vector similarity search

・ Google Places API – Location, photos, ratings

・ Geopy – Geocoding & distance calculation

・ LINE Messaging API – Sending messages & Flex templates

・ Docker – Containerized deployment

・ Pydantic – Data validation

★ Features★ 
==================================================================================================================================================

・ Location-aware search – Extracts location names from user queries and prioritizes nearby stores

・ Ramen store recommendations – FAISS similarity search from a ramen dataset

・ Google Places API integration – Fetches photos, ratings, and reviews count

・ LINE Flex Messages – Rich cards with store name, rating (stars), photo, address, features, and map button

・ Multi-language support – Automatically translates results to the user’s language

・ FastAPI backend – Handles LINE webhook requests efficiently


★ How It Works★ 
==================================================================================================================================================

User sends a ramen-related message to the LINE bot

Bot extracts location keywords (if any)

Searches FAISS vector store for similar restaurants

Ranks results by distance if location is provided

Fetches additional info from Google Places API

Returns top 3 results as LINE Flex Messages
