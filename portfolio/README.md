# Port Security Spoofing Detection – Portfolio Site

Static site to showcase the project, methods, and code snippets. Ready for Netlify.

## Structure
- `index.html` – Overview and hero
- `methods.html` – Detection methods with JSON snippets and explanations
- `code.html` – Key code excerpts with commentary
- `demo.html` – Links to local demos and video/GIF screenshot placeholders
- `assets/` – CSS, JS, images

## Local preview
Use any static server (e.g., Python):

```bash
cd portfolio
python3 -m http.server 5500
```

Open `http://localhost:5500`.

## Netlify deploy
- Drag-and-drop the `portfolio/` folder into Netlify
- Or connect to a repo and set publish directory to `portfolio/`
- No build step required

## Live demo links (edit as needed)
- Main app: `http://localhost:8000/`
- Dashboard: `http://localhost:8001/`
- Dead reckoning map (synthetic): `http://localhost:8000/api/dead-reckoning/map/synthetic`

Update these to public URLs when available.
