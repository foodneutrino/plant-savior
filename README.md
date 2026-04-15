# Plant Savior

A plant watering reminder app that uses Google Calendar to send push notifications to your phone. When a reminder fires, tap the link in the event to mark the plant as watered or defer to tomorrow.

## How It Works

1. Add a plant via the web UI — the app creates a Google Calendar event for the next watering date
2. Google Calendar sends a push notification to your phone on that date
3. Tap the link in the event description to open the response page
4. Choose **"Yes, I Watered It"** → next reminder in N days (based on the plant's interval)
5. Choose **"Not Yet"** → reminder again tomorrow

The app includes default watering intervals for ~30 common houseplants. You can also set a custom interval for any plant.

## Setup

### 1. Google Calendar API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Google Calendar API** (APIs & Services → Library → search "Calendar")
4. Create OAuth2 credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Download the JSON file and save it as `credentials.json` in this directory

### 2. Install Dependencies

```bash
cd plant-savior
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:
- `CALENDAR_ID` — your Google Calendar ID (usually your Gmail address)
- `BASE_URL` — the URL where this app is reachable from your phone (see [Accessing from Your Phone](#accessing-from-your-phone))
- `REMINDER_HOUR` — hour of day (0–23) for watering reminders (default: 9)

### 4. Authenticate with Google

```bash
python auth.py
```

This opens a browser for Google OAuth2 consent. Grant calendar access and a `token.json` file will be saved. You only need to do this once.

### 5. Run the App

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## Accessing from Your Phone

The `BASE_URL` in `.env` must be reachable from your phone so the Google Calendar event link works. Options:

### Tailscale (recommended)
Install [Tailscale](https://tailscale.com/) on your host machine and phone. Set `BASE_URL` to `http://<tailscale-hostname>:8000`. No port forwarding needed.

### ngrok (quick testing)
```bash
ngrok http 8000
```
Set `BASE_URL` to the generated `https://...ngrok-free.app` URL. Note: the free URL changes each time.

### Deploy to a server
Run on a VPS or a Raspberry Pi that's always on. Use a reverse proxy (nginx/caddy) for HTTPS.

## Project Structure

```
plant-savior/
  main.py                 # FastAPI app — routes and request handling
  auth.py                 # Google OAuth2 flow (run once to get token.json)
  calendar_service.py     # Create, delete, and reschedule Google Calendar events
  database.py             # SQLite schema and CRUD operations
  models.py               # Pydantic request/response models
  plant_data.py           # Default watering intervals for common houseplants
  templates/
    base.html             # Shared mobile-optimized layout
    plants.html           # Plant list + add plant form
    water.html            # "Watered" / "Not Yet" action page
    confirmed.html        # Confirmation after watering action
  requirements.txt
  .env.example            # Template for environment variables
```

## Default Plant Intervals

The app knows default watering intervals for common plants like:

| Plant | Interval |
|-------|----------|
| Basil, Mint | 3 days |
| Peace Lily, Calathea, Boston Fern | 5 days |
| Monstera, Pothos, Spider Plant | 7 days |
| Rubber Plant, Dracaena, Rosemary | 10 days |
| Snake Plant, Aloe Vera, Succulent, ZZ Plant | 14 days |
| Cactus | 21 days |

When adding a plant, type the name and the app will auto-suggest an interval. You can always override it with a custom value.
