# Test Data Seed for Screenshots & Demo

## Overview

Script **`scripts/seed-test-data.sh`** creates complete demo content for testing and README screenshots. All content is in English with realistic fishing forum structure.

## What Gets Created

### Test User
```
Email:    demo@fishingforum.test
Password: TestPassword123!
Username: demouser
```

### Category: "Carp Fishing"
**Description:** Techniques, tips, and strategies for successful carp fishing. Share your catches, discuss tackle, and connect with other carp anglers.

**Features:**
- Can accept category icon (optional image upload)
- All posts are in this category
- Owned by test user

### Posts (3 total)

#### 1. **Monster Carp Caught at Dawn — 52 lbs!**
- **Type:** Success story / catch report
- **Content:** Personal catch narrative with markdown formatting
- **Includes:**
  - H1 and H2 headers
  - Bold text (**important words**)
  - Numbered and bullet lists
  - Photo placeholder comment: `*[Photo of the catch would go here]*`
- **Engagement:** 2 follow-up comments with photo placeholders

#### 2. **Beginner's Guide: Essential Carp Fishing Tackle**
- **Type:** Educational guide
- **Content:** Structured how-to post for new anglers
- **Includes:**
  - Checklist format
  - Table (markdown)
  - Cost estimate
  - Knot learning section with image placeholder
- **Engagement:** 2 beginner questions/comments with avatar placeholders

#### 3. **Spring Season Forecast: Water Temperature & Feeding Patterns**
- **Type:** Seasonal guide / strategy
- **Content:** Data-driven post with temperature breakpoints
- **Includes:**
  - Data table with formatting
  - Best practices
  - Moon phase mention
  - Chart placeholder for graphs
- **Engagement:** 1 technical follow-up question

### Comments (5 total)
Each comment includes:
- Realistic Q&A engagement
- Photo/avatar placeholders in markdown:
  - `*[Your angler profile photo would appear here]*`
  - `*[User avatar placeholder]*`
  - `*[Awaiting angler photo]*`

This shows where profile pictures, user avatars, and attached images would load.

---

## Usage

### Prerequisites
- Forum running at `http://localhost:8000` (or provide custom URL)
- PostgreSQL database available
- Backend fully initialized (`alembic upgrade head` completed)
- `curl` installed (standard on Linux/macOS, Windows 10+)

### Run the Script

**Basic (default local):**
```bash
bash scripts/seed-test-data.sh
```

**Custom API URL:**
```bash
bash scripts/seed-test-data.sh http://192.168.1.100:8000
```

**In Kubernetes (port-forward first):**
```bash
kubectl -n forum-wedkarskie port-forward svc/backend 8000:8000 &
bash scripts/seed-test-data.sh http://localhost:8000
```

### Expected Output
```
$ bash scripts/seed-test-data.sh http://localhost:8000
🎣 Fishing Forum — Seed Test Data
=================================

1️⃣  Registering test user...
✅ User registered: demo@fishingforum.test

2️⃣  Logging in...
✅ Logged in successfully

3️⃣  Creating category: Carp Fishing...
✅ Category created: 'Carp Fishing' (ID: 12345678-...)

5️⃣  Creating demo posts...
  ✅ Post 1: Monster Carp Caught at Dawn — 52 lbs!
  ✅ Post 2: Beginner's Guide: Essential Carp Fishing Tackle
  ✅ Post 3: Spring Season Forecast: Water Temperature & Feeding Patterns

6️⃣  Creating demo comments with image placeholders...
  ✅ Comment added to post 1
  ✅ Comment added to post 1
  ✅ Comment added to post 2
  ✅ Comment added to post 2
  ✅ Comment added to post 3

=================================
🎉 Seed Data Complete!
=================================

Test User:
  Email:    demo@fishingforum.test
  Password: TestPassword123!
  Username: demouser

Created Content:
  Category: Carp Fishing
  Posts:    3
  Comments: 5

Forum URL: http://localhost:8000
```

---

## For README Screenshots

### Navigation Flow for Demo
1. **Login page** — Use test credentials above
2. **Homepage** — "Carp Fishing" category visible in category list
3. **Category view** — Click "Carp Fishing" to see all 3 posts
4. **Post detail** — Click any post to see:
   - Full markdown content with formatted text
   - Comment thread with 1–2 comments
   - Image placeholders in markdown and comments
   - Like button engagement
   - User profile info in sidebar (if available)

### Ideal Screenshots
- **Login flow:** Before/after auth
- **Homepage:** Category cards with icon
- **Category view:** Keyset pagination with posts
- **Post detail:** Markdown rendering + comment thread
- **Admin panel:** (separate admin user if needed)

---

## Reset Data

To clean up and re-seed:

```bash
# Option 1: Delete user (keeps database schema)
docker exec -it forum-wedkarskie-postgres psql -U postgres -d forum_wedkarskie \
  -c "DELETE FROM users WHERE email = 'demo@fishingforum.test';"

# Option 2: Full database reset
docker compose down -v && docker compose up --build

# Then re-run the seed script
bash scripts/seed-test-data.sh
```

---

## Customization

Edit **`scripts/seed-test-data.sh`** to modify:
- Test user credentials (lines 9-11: `TEST_EMAIL`, `TEST_PASSWORD`, `TEST_USERNAME`)
- Category name/description (line 50+: `Carp Fishing`)
- Post titles/content (lines 97+, 128+, 157+: `POST*_CONTENT`)
- Comment text (lines 185+: curl requests with `"content":` fields)

All strings are UTF-8 text — save file with UTF-8 encoding.

---

## Notes

- **Idempotent on registration:** If user exists, script skips registration and logs in instead.
- **Category ownership:** All posts are created by the test user; they own the category.
- **Image placeholders:** Comments include markdown placeholders for angler photos. No actual images are seeded in comments (only category icon optional).
- **Permissions:** Test user gets standard `user` role; create post/comment permissions flow from there.
- **Dates:** Created posts show `created_at` = server time (UTC).

---

## API Endpoints Called

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/register` | POST | Create test user |
| `/api/v1/auth/login` | POST | Obtain access token |
| `/api/v1/categories` | POST | Create category |
| `/api/v1/files` | POST | Upload category image (optional) |
| `/api/v1/categories/{id}/image` | POST | Assign image to category |
| `/api/v1/posts` | POST | Create posts |
| `/api/v1/posts/{id}/comments` | POST | Create comments |

All requests authenticated with Bearer token from login.
