# API Documentation - Medical Fake News Detection System

## Base URL
```
http://localhost:5000/api
```

## Authentication
Most endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

## Response Format
All API responses follow this structure:
```json
{
  "message": "Success/error message",
  "status": "success|error",
  "data": {...}  // Optional, contains response data
}
```

## Error Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request / Validation Error
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `409` - Conflict (e.g., duplicate resource)
- `429` - Too Many Requests
- `500` - Internal Server Error

## Endpoints Overview

### Authentication
- [POST /register](#post-register) - Register new user
- [POST /login](#post-login) - User login

### Campaigns
- [GET /campaigns](#get-campaigns) - List user campaigns
- [POST /campaigns](#post-campaigns) - Create new campaign
- [GET /campaigns/{id}](#get-campaignsid) - Get campaign details
- [PUT /campaigns/{id}](#put-campaignsid) - Update campaign
- [DELETE /campaigns/{id}](#delete-campaignsid) - Delete campaign

### Data Collection
- [POST /collect](#post-collect) - Trigger data collection
- [GET /trends](#get-trends) - Get trending topics

### Analysis
- [POST /analysis/trigger](#post-analysistriggr) - Trigger analysis
- [GET /posts](#get-posts) - Get analyzed posts

### Reports
- [GET /campaigns/{id}/report](#get-campaignsidreport) - Generate campaign report

---

## Detailed Endpoints

### POST /register

Register a new user account.

**Request Body:**
```json
{
  "username": "string (min 3 chars)",
  "email": "string (valid email)",
  "password": "string (min 8 chars, uppercase, lowercase, number)"
}
```

**Response 201:**
```json
{
  "message": "Registrazione avvenuta con successo!",
  "status": "success",
  "user_id": "string"
}
```

**Response 400:**
```json
{
  "message": "Validation error details",
  "status": "error"
}
```

**Response 409:**
```json
{
  "message": "Email già registrata",
  "status": "error"
}
```

### POST /login

Authenticate existing user.

**Request Body:**
```json
{
  "email": "string (email or username)",
  "password": "string"
}
```

**Response 200:**
```json
{
  "message": "Login avvenuto con successo!",
  "status": "success",
  "token": "jwt_token_string",
  "user": {
    "id": "string",
    "username": "string",
    "email": "string"
  }
}
```

**Response 401:**
```json
{
  "message": "Credenziali non valide",
  "status": "error"
}
```

### GET /campaigns

Get list of user's campaigns.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `status` (optional): Filter by status (`active`, `finished`, `closed`)
- `limit` (optional): Number of results (default: 20)
- `offset` (optional): Pagination offset (default: 0)

**Response 200:**
```json
{
  "campaigns": [
    {
      "id": "string",
      "name": "string",
      "keywords": ["string"],
      "social_platforms": ["string"],
      "status": "active|finished|closed",
      "start_date": "ISO date",
      "end_date": "ISO date",
      "created_at": "ISO date",
      "posts_count": number,
      "analysis_stats": {
        "total_analyzed": number,
        "fake_news_detected": number
      }
    }
  ],
  "total": number,
  "status": "success"
}
```

### POST /campaigns

Create a new monitoring campaign.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "name": "string",
  "keywords": ["string"],
  "social_platforms": ["twitter", "reddit", "youtube", "facebook", "news"],
  "start_date": "YYYY-MM-DD (optional, defaults to today)",
  "end_date": "YYYY-MM-DD (optional, defaults to +30 days)",
  "description": "string (optional)"
}
```

**Response 201:**
```json
{
  "message": "Campagna creata con successo!",
  "status": "success",
  "campaign_id": "string"
}
```

### GET /campaigns/{id}

Get detailed information about a specific campaign.

**Headers:**
```
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "campaign": {
    "id": "string",
    "name": "string",
    "keywords": ["string"],
    "social_platforms": ["string"],
    "status": "string",
    "start_date": "ISO date",
    "end_date": "ISO date",
    "created_at": "ISO date",
    "updated_at": "ISO date",
    "description": "string",
    "posts_count": number,
    "analysis_stats": {
      "total_posts": number,
      "analyzed_posts": number,
      "fake_news_detected": number,
      "accuracy_metrics": {
        "precision": number,
        "recall": number,
        "f1_score": number
      }
    }
  },
  "status": "success"
}
```

### PUT /campaigns/{id}

Update an existing campaign.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:** (all fields optional)
```json
{
  "name": "string",
  "keywords": ["string"],
  "social_platforms": ["string"],
  "description": "string"
}
```

**Response 200:**
```json
{
  "message": "Campagna modificata con successo!",
  "status": "success"
}
```

### DELETE /campaigns/{id}

Delete a campaign and all associated data.

**Headers:**
```
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "message": "Campagna eliminata con successo!",
  "status": "success"
}
```

### POST /collect

Trigger data collection from social media platforms.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "query": "string (search terms)",
  "source": "all|twitter|reddit|youtube|facebook|news",
  "max_results": number (optional, default: 100)
}
```

**Response 200:**
```json
{
  "message": "Raccolta dati avviata",
  "status": "success",
  "collection_id": "string"
}
```

### GET /trends

Get current trending topics related to medical/health keywords.

**Headers:**
```
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "trends": [
    {
      "keyword": "string",
      "volume": number,
      "growth": number,
      "related_terms": ["string"]
    }
  ],
  "generated_at": "ISO date",
  "status": "success"
}
```

### POST /analysis/trigger

Trigger analysis of collected posts.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "batch_size": number (optional, default: 50)
}
```

**Response 200:**
```json
{
  "message": "Analisi avviata",
  "status": "success",
  "analysis_id": "string"
}
```

### GET /posts

Get analyzed social media posts.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `campaign_id` (optional): Filter by campaign
- `platform` (optional): Filter by platform
- `analyzed` (optional): Filter by analysis status (true/false)
- `fake_news_score` (optional): Filter by score range (e.g., "3-5")
- `limit` (optional): Number of results (default: 20)
- `offset` (optional): Pagination offset

**Response 200:**
```json
{
  "posts": [
    {
      "id": "string",
      "text": "string",
      "platform": "string",
      "author": "string",
      "created_at": "ISO date",
      "url": "string",
      "analysis_results": {
        "grado_disinformazione": number,
        "valutazione_testuale": "string",
        "motivazione": "string",
        "sentiment": "positivo|neutro|negativo",
        "medical_concepts": ["string"],
        "key_terms": ["string"],
        "pubmed_validation": [
          {
            "title": "string",
            "authors": ["string"],
            "doi": "string",
            "relevance_score": number
          }
        ],
        "confidence_score": number
      }
    }
  ],
  "total": number,
  "status": "success"
}
```

### GET /campaigns/{id}/report

Generate comprehensive report for a campaign.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `format` (optional): Response format (`json` or `pdf`, default: json)

**Response 200:**
```json
{
  "report": {
    "campaign_info": {
      "name": "string",
      "period": "string",
      "keywords": ["string"]
    },
    "summary": {
      "total_posts": number,
      "fake_news_detected": number,
      "fake_news_percentage": number,
      "most_affected_platform": "string"
    },
    "platform_breakdown": {
      "twitter": {"posts": number, "fake_news": number},
      "reddit": {"posts": number, "fake_news": number}
    },
    "timeline": [
      {
        "date": "YYYY-MM-DD",
        "posts": number,
        "fake_news": number
      }
    ],
    "top_fake_news": [
      {
        "post_id": "string",
        "text": "string",
        "platform": "string",
        "score": number,
        "engagement": number
      }
    ],
    "medical_concepts": [
      {
        "concept": "string",
        "frequency": number,
        "fake_news_association": number
      }
    ]
  },
  "status": "success"
}
```

## Error Handling Examples

### Validation Error
```json
{
  "message": "Missing required fields: email, password",
  "status": "error",
  "missing_fields": ["email", "password"]
}
```

### Authentication Error
```json
{
  "message": "Token JWT scaduto",
  "status": "error"
}
```

### Rate Limit Error
```json
{
  "message": "Rate limit exceeded. Please try again later.",
  "status": "error"
}
```

## Rate Limiting

API endpoints are rate limited to prevent abuse:
- Authentication endpoints: 5 requests per minute
- Data collection: 10 requests per hour
- General API: 100 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Pagination

List endpoints support pagination:
```
GET /posts?limit=20&offset=40
```

Response includes pagination metadata:
```json
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 40,
    "has_next": true,
    "has_prev": true
  }
}
```