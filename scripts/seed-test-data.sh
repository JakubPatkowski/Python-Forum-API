#!/bin/bash
# Seed test data for Fishing Forum screenshots and demo
# Usage: ./seed-test-data.sh [API_URL]
#        ./seed-test-data.sh -ApiUrl http://localhost:8000   (PowerShell-style flag also accepted)
# Idempotent: skips creation if user/category/post already exists.

set -e

# Accept both a positional URL and the PowerShell-style "-ApiUrl <url>" flag,
# so copy-pasting the .ps1 invocation does not silently break the script.
API_URL=""
while [ $# -gt 0 ]; do
  case "$1" in
    -ApiUrl|-apiurl|--api-url) API_URL="$2"; shift 2 ;;
    -*) echo "⚠️  Unknown flag '$1' — ignoring"; shift ;;
    *) API_URL="$1"; shift ;;
  esac
done
API_URL="${API_URL:-http://localhost:8000}"
TEST_EMAIL="demo@fishingforum.com"
TEST_PASSWORD="TestPassword123!"
TEST_USERNAME="demouser"

# Parse a top-level string field from a JSON object.
# Usage: json_field <field> <json>
json_field() {
  local field="$1"
  local json="$2"
  echo "$json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
v = d.get('$field', '')
if v:
    print(v)
" 2>/dev/null || true
}

echo "🎣 Fishing Forum — Seed Test Data"
echo "================================="
echo ""

# ============================================
# 1. Register test user
# ============================================
echo "1️⃣  Registering test user..."

REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"username\": \"$TEST_USERNAME\",
    \"password\": \"$TEST_PASSWORD\"
  }" 2>/dev/null)

if echo "$REGISTER_RESPONSE" | grep -q "access_token"; then
  echo "✅ User registered: $TEST_EMAIL"
elif echo "$REGISTER_RESPONSE" | grep -q "USERNAME_TAKEN\|EMAIL_TAKEN"; then
  echo "⚠️  User already exists, skipping registration"
else
  echo "Registration response: $REGISTER_RESPONSE"
fi

# ============================================
# 2. Login
# ============================================
echo ""
echo "2️⃣  Logging in..."

LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"login\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\"
  }")

ACCESS_TOKEN=$(json_field access_token "$LOGIN_RESPONSE")

if [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ Login failed"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "✅ Logged in successfully"

AUTH_HEADER="Authorization: Bearer $ACCESS_TOKEN"
JSON_HEADER="Content-Type: application/json"

# ============================================
# 2b. Fetch current user ID (for post lookup)
# ============================================
ME_RESPONSE=$(curl -s "$API_URL/api/v1/users/me" -H "$AUTH_HEADER")
USER_ID=$(json_field id "$ME_RESPONSE")

# ============================================
# 3. Create or fetch category
# ============================================
echo ""
echo "3️⃣  Creating category: Carp Fishing..."

CATEGORY_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/categories" \
  -H "$JSON_HEADER" \
  -H "$AUTH_HEADER" \
  -d '{
    "name": "Carp Fishing",
    "description": "Techniques, tips, and strategies for successful carp fishing. Share your catches, discuss tackle, and connect with other carp anglers."
  }')

CATEGORY_ID=$(json_field id "$CATEGORY_RESPONSE")

if [ -z "$CATEGORY_ID" ]; then
  if echo "$CATEGORY_RESPONSE" | grep -q "CATEGORY_EXISTS"; then
    echo "⚠️  Category already exists, fetching ID..."
    CATEGORIES_LIST=$(curl -s "$API_URL/api/v1/categories" -H "$AUTH_HEADER")
    CATEGORY_ID=$(echo "$CATEGORIES_LIST" | python3 -c "
import sys, json
for c in json.load(sys.stdin):
    if c.get('name') == 'Carp Fishing':
        print(c['id'])
        break
" 2>/dev/null || true)
  fi
fi

if [ -z "$CATEGORY_ID" ]; then
  echo "❌ Failed to create/find category"
  echo "Response: $CATEGORY_RESPONSE"
  exit 1
fi

echo "✅ Category ready: 'Carp Fishing' (ID: $CATEGORY_ID)"

# ============================================
# 4. Helper: get or create a post by title
# ============================================
# Fetches existing post ID for this user by title, or creates it.
# Prints the post ID to stdout; prints status to stderr.
get_or_create_post() {
  local title="$1"
  local payload="$2"

  # Check if the post already exists for this user
  if [ -n "$USER_ID" ]; then
    POSTS_LIST=$(curl -s "$API_URL/api/v1/posts?author_id=$USER_ID&limit=100" -H "$AUTH_HEADER")
    EXISTING_ID=$(echo "$POSTS_LIST" | python3 -c "
import sys, json
title = $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$title")
data = json.load(sys.stdin)
for p in data.get('items', []):
    if p.get('title') == title:
        print(p['id'])
        break
" 2>/dev/null || true)
    if [ -n "$EXISTING_ID" ]; then
      echo "⚠️  Already exists, reusing" >&2
      echo "$EXISTING_ID"
      return
    fi
  fi

  # Create the post
  RESP=$(curl -s -X POST "$API_URL/api/v1/posts" \
    -H "$JSON_HEADER" \
    -H "$AUTH_HEADER" \
    -d "$payload")
  json_field id "$RESP"
}

# ============================================
# 5. Create demo posts
# ============================================
echo ""
echo "4️⃣  Creating demo posts..."

# Post 1
POST1_TITLE="Monster Carp Caught at Dawn — 52 lbs!"
POST1_CONTENT="# My Personal Best!

Yesterday morning, after three nights of camping by the lake, I finally landed the fish of a lifetime — a **52 lb mirror carp**!

## The Setup
- **Location:** Stillwater Lake, North Bank
- **Time:** 5:47 AM
- **Weather:** Overcast, light breeze
- **Rig:** 25 lb test, size 4 hook, corn sweetener boilie

The fight lasted almost 15 minutes. My heart was pounding the entire time!

## Key Tips
1. **Patience is everything** — I waited three nights for this opportunity
2. **Quality boilie selection** — Fresh corn-based baits work best at dawn
3. **Rod stability** — Invest in a good rod rest; it saved this catch
4. **Land the fish slowly** — No rushing; let the rod do the work

*[Photo of the catch would go here]*

Would love to hear about your personal best! Drop your stories in the comments below."

POST1_PAYLOAD=$(python3 -c "
import json, sys
title = sys.argv[1]
content = sys.argv[2]
cat = sys.argv[3]
print(json.dumps({'category_id': cat, 'title': title, 'content': content}))
" "$POST1_TITLE" "$POST1_CONTENT" "$CATEGORY_ID")

POST1_STATUS=""
POST1_ID=$(get_or_create_post "$POST1_TITLE" "$POST1_PAYLOAD" 2>/tmp/post_status)
POST1_STATUS=$(cat /tmp/post_status)
if [ -n "$POST1_ID" ]; then
  echo "  ✅ Post 1: $POST1_TITLE ${POST1_STATUS:+(${POST1_STATUS})}"
else
  echo "  ❌ Failed to create post 1"
fi

# Post 2
POST2_TITLE="Beginner's Guide: Essential Carp Fishing Tackle"
POST2_CONTENT="# Getting Started with Carp Fishing

Thinking about taking up carp fishing? Here's everything you need to get started.

## Essential Gear Checklist
- **Rod:** 12–13 ft medium-heavy action
- **Reel:** Baitrunner or freespool reel (minimum 5000 size)
- **Line:** 20–25 lb monofilament or braid
- **Hooks:** Size 2–4 barbless (UK rules)
- **Boilies:** Fishmeal or corn-based varieties
- **Pod:** Three-rod pod with bite alarm

## Knot Guide
Master these essential knots:
- Improved Clinch Knot (for hook attachment)
- Palomar Knot (for line-to-reel)
- Albright Knot (for splicing leaders)

*[Diagram and image placeholders for knot-tying would go here]*

## Cost Breakdown
A complete beginner setup runs about \$300–\$500 USD. You don't need expensive gear to start — consistency and technique matter more!

Feel free to ask questions in the comments. What's your setup?"

POST2_PAYLOAD=$(python3 -c "
import json, sys
title = sys.argv[1]
content = sys.argv[2]
cat = sys.argv[3]
print(json.dumps({'category_id': cat, 'title': title, 'content': content}))
" "$POST2_TITLE" "$POST2_CONTENT" "$CATEGORY_ID")

POST2_ID=$(get_or_create_post "$POST2_TITLE" "$POST2_PAYLOAD" 2>/tmp/post_status)
POST2_STATUS=$(cat /tmp/post_status)
if [ -n "$POST2_ID" ]; then
  echo "  ✅ Post 2: $POST2_TITLE ${POST2_STATUS:+(${POST2_STATUS})}"
else
  echo "  ❌ Failed to create post 2"
fi

# Post 3
POST3_TITLE="Spring Season Forecast: Water Temperature & Feeding Patterns"
POST3_CONTENT="# Spring Carp Fishing Strategy

As we head into spring, water temperatures are rising and carp feeding patterns change. Here's what you need to know.

## Temperature Milestones
| Temperature | Behavior | Best Time |
|-------------|----------|-----------|
| 38–46°F     | Dormant, slow feeding | Midday warmth |
| 46–55°F     | Feeding increases | Dusk to dawn |
| 55–65°F     | Very active | All day |
| 65°F+       | Peak activity | Early morning |

## Recommended Tactics
- **High protein boilies** stimulate feeding
- **Smaller portions** — frequent light feeding > heavy baiting
- **Dawn and dusk** are golden hours
- **Moon phase** matters — full moon = better feeding

*[Charts and water temperature map would go here]*

Based on the forecast, expect excellent fishing in late April and May. The key is adapting to daily temperature swings.

What's your spring forecast looking like? Let's discuss in the comments!"

POST3_PAYLOAD=$(python3 -c "
import json, sys
title = sys.argv[1]
content = sys.argv[2]
cat = sys.argv[3]
print(json.dumps({'category_id': cat, 'title': title, 'content': content}))
" "$POST3_TITLE" "$POST3_CONTENT" "$CATEGORY_ID")

POST3_ID=$(get_or_create_post "$POST3_TITLE" "$POST3_PAYLOAD" 2>/tmp/post_status)
POST3_STATUS=$(cat /tmp/post_status)
if [ -n "$POST3_ID" ]; then
  echo "  ✅ Post 3: $POST3_TITLE ${POST3_STATUS:+(${POST3_STATUS})}"
else
  echo "  ❌ Failed to create post 3"
fi

# ============================================
# 6. Create demo comments
# ============================================
echo ""
echo "5️⃣  Creating demo comments..."

if [ -n "$POST1_ID" ]; then
  curl -s -X POST "$API_URL/api/v1/posts/$POST1_ID/comments" \
    -H "$JSON_HEADER" \
    -H "$AUTH_HEADER" \
    -d '{"content": "Amazing catch! That mirror pattern is beautiful. I'\''m curious about your exact location — was it a known spot or did you scout it yourself?\n\n*[Your angler profile photo would appear here]*\n\nLooking forward to more posts like this!"}' \
    > /dev/null
  echo "  ✅ Comment added to post 1"

  curl -s -X POST "$API_URL/api/v1/posts/$POST1_ID/comments" \
    -H "$JSON_HEADER" \
    -H "$AUTH_HEADER" \
    -d '{"content": "The fight duration is impressive! Did you have rod bow going the entire time? I find that most of my fights result in either quick hooksets or complete misses.\n\n*[Awaiting angler photo]*"}' \
    > /dev/null
  echo "  ✅ Comment added to post 1"
fi

if [ -n "$POST2_ID" ]; then
  curl -s -X POST "$API_URL/api/v1/posts/$POST2_ID/comments" \
    -H "$JSON_HEADER" \
    -H "$AUTH_HEADER" \
    -d '{"content": "Great beginner'\''s guide! Just starting out myself and this is super helpful. One question — what'\''s the best brand for starter boilies you'\''d recommend?\n\n*[New angler profile picture would load here]*"}' \
    > /dev/null
  echo "  ✅ Comment added to post 2"

  curl -s -X POST "$API_URL/api/v1/posts/$POST2_ID/comments" \
    -H "$JSON_HEADER" \
    -H "$AUTH_HEADER" \
    -d '{"content": "The Albright knot took me forever to master. Any chance you could post a video tutorial? Would help a lot of us visual learners.\n\n*[User avatar placeholder]*"}' \
    > /dev/null
  echo "  ✅ Comment added to post 2"
fi

if [ -n "$POST3_ID" ]; then
  curl -s -X POST "$API_URL/api/v1/posts/$POST3_ID/comments" \
    -H "$JSON_HEADER" \
    -H "$AUTH_HEADER" \
    -d '{"content": "These temperature breakpoints are exactly what I needed! Is this based on your personal experience or scientific research? Would love to see the full data.\n\n*[Commenter profile image to be loaded]*"}' \
    > /dev/null
  echo "  ✅ Comment added to post 3"
fi

# ============================================
# Summary
# ============================================
echo ""
echo "================================="
echo "🎉 Seed Data Complete!"
echo "================================="
echo ""
echo "Test User:"
echo "  Email:    $TEST_EMAIL"
echo "  Password: $TEST_PASSWORD"
echo "  Username: $TEST_USERNAME"
echo ""
echo "Created Content:"
echo "  Category: Carp Fishing"
echo "  Posts:    3"
echo "  Comments: 5"
echo ""
echo "Forum URL: $API_URL"
echo ""
