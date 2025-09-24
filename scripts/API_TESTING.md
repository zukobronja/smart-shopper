# API Testing Guide

## Setup

1. **Start the API server:**
   ```bash
   uv run app.py
   ```

2. **Import Insomnia Collection:**
   - Open Insomnia
   - Import `insomnia_collection.json`
   - Set base_url environment variable to `http://localhost:8000`

## Testing Workflow

### 1. Health Checks
- **Basic Health:** `GET /health`
- **V1 Health:** `GET /v1/health`

Both should return status "healthy"

### 2. User Registration
- **Register User:** `POST /auth/register`
- Use the provided JSON body with email/password/full_name
- Should return user object with status "pending"

### 3. User Activation (Required for Login)
Since users start as "pending", activate them for testing:

```bash
python scripts/activate_user.py john.doe@example.com
```

### 4. User Login
- **Login User:** `POST /auth/login`
- Uses form-encoded data (username=email, password=password)
- Should return login success message with user object
- Sets HTTP-only cookies for authentication

### 5. Authenticated Requests
- **Get Current User:** `GET /auth/me`
- Requires valid authentication
- For testing with Authorization header, extract access_token from login response

### 6. Product Search (Stub)
- **Search Products:** `POST /v1/search`
- Optional authentication (works with or without login)
- Currently returns stub response indicating LangGraph not implemented

### 7. Logout
- **Logout User:** `POST /auth/logout`
- Clears authentication cookies
- Should return logout success message

## Important Notes

- **Cookie Authentication:** The API uses HTTP-only cookies, which Insomnia may not handle automatically
- **Manual Token Testing:** For `/auth/me`, you may need to manually extract the access_token from login response and add it to the Authorization header
- **User Status:** New users start as "pending" and must be activated before login
- **Search Endpoint:** Currently returns stub response - full implementation coming in Phase 3

## Environment Variables

Make sure these are set in your `.env` file:
```env
ENVIRONMENT=development
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=smartshopper
JWT_SECRET_KEY=your-secret-key-change-in-production
```

## Troubleshooting

- **MongoDB Connection:** Ensure MongoDB is running locally or set correct connection string
- **Port Conflicts:** Default port is 8000, change in app.py if needed
- **Authentication Issues:** Check JWT_SECRET_KEY is set and user is activated
- **CORS Issues:** Frontend requests from different origin should work with current CORS settings