# Demolate Records — Landing Page

Static single-file landing page for Demolate Records, a Berlin techno label launching June 5, 2026.

## Preview locally

```bash
# Option 1: Python (recommended — serves fonts correctly)
python3 -m http.server 8080
# then open http://localhost:8080

# Option 2: Open directly
open index.html          # macOS
xdg-open index.html      # Linux
```

> Note: Opening `index.html` directly (`file://`) works for layout but Google Fonts may be blocked by some browsers in `file://` context. Use the Python server for accurate rendering.

## Stack

- Single `index.html`, no build step
- Tailwind CSS via CDN (`cdn.tailwindcss.com`)
- Archivo Black + Inter via Google Fonts
- Zero JavaScript beyond Tailwind config

## Files

```
demolate-landing/
├── index.html              # Full page (< 60KB)
├── README.md               # This file
└── assets/
    └── demolate-logo.svg   # Label logo (black SVG, inverted white via CSS)
```

## Deploy

**GitHub Pages**
1. Push repo to GitHub
2. Settings → Pages → Source: `main` branch, `/ (root)`
3. Site available at `https://<username>.github.io/<repo>/`

**Netlify (drag and drop)**
1. Go to app.netlify.com → Add new site → Deploy manually
2. Drag the `demolate-landing/` folder into the drop zone
3. Done — live URL provided instantly

**Vercel**
```bash
npx vercel --yes
```

## Screenshot

No headless browser was available at build time (`chromium`, `google-chrome`, and `playwright` not installed). To capture a screenshot manually:

```bash
chromium --headless --screenshot=screenshot.png --window-size=1920,1080 \
  "file:///path/to/demolate-landing/index.html"
```

## Design

- Aesthetic: brutalist / exaggerated minimalism
- Colors: `#000` bg / `#FFF` fg / `#FF0000` accent
- Typography: Archivo Black (display) / Inter (body)
- No border-radius, no transitions, no animations
- Responsive: 375px mobile → 1280px+ desktop
