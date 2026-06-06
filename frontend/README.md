# ESG Claim Verification Assistant - Frontend

React + Vite frontend for the ESG Claim Verification Assistant.

## Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Development

The frontend runs on `http://localhost:3000` and proxies API requests to the backend at `http://localhost:8000`.

## Structure

```
src/
├── components/       # React components
├── services/         # API service layer
├── App.jsx          # Main application component
├── main.jsx         # Application entry point
└── index.css        # Global styles with Tailwind
```

## Features

- **Three-pane dashboard layout**
  - Left: PDF document viewer
  - Center: Extracted claims table
  - Right: Evidence and AI explanation

- **Upload flow**
  - Drag-and-drop PDF upload
  - Real-time processing status
  - Progress indicators

- **Interactive claims**
  - Click to view evidence
  - Confidence scores
  - Page number references

- **Evidence visualization**
  - Leaflet map with facility markers
  - NASA FIRMS anomaly overlays
  - GDELT news timeline

- **Risk scoring**
  - Color-coded gauge (red/amber/green)
  - Transparent breakdown
  - AI-generated explanation

## Technologies

- **React 18** - UI framework
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **react-pdf** - PDF viewer
- **react-leaflet** - Interactive maps
- **axios** - HTTP client

## Notes

This is a basic structure for the hackathon demo. For production:
- Add proper error handling
- Implement loading states
- Add form validation
- Include accessibility features
- Add unit tests