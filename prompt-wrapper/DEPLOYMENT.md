# Production Deployment Guide

## Recommended Hosting Options

### 🥇 **1. Vercel** (Recommended - Easiest)
**Best for:** Quick deployment, automatic HTTPS, great DX

**Pros:**
- Free tier with generous limits
- Automatic deployments from Git
- Built-in CDN and HTTPS
- Zero configuration needed
- Custom domains
- Preview deployments for PRs

**Steps:**
1. Push your code to GitHub/GitLab/Bitbucket
2. Go to [vercel.com](https://vercel.com) and sign up
3. Click "New Project" and import your repository
4. Vercel auto-detects Create React App - just click "Deploy"
5. Done! Your app is live in ~2 minutes

**Cost:** Free for personal projects, $20/month for teams

---

### 🥈 **2. Netlify** (Also Excellent)
**Best for:** Static sites, form handling, serverless functions

**Pros:**
- Free tier with 100GB bandwidth/month
- Drag-and-drop deployment option
- Automatic HTTPS
- Built-in form handling
- Preview deployments

**Steps:**
1. Build your app: `npm run build`
2. Go to [netlify.com](https://netlify.com) and sign up
3. Drag the `build` folder to Netlify's deploy area
4. Or connect your Git repo for auto-deployments

**Cost:** Free for personal projects, $19/month for Pro

---

### 🥉 **3. GitHub Pages** (Free & Simple)
**Best for:** Open source projects, simple deployments

**Pros:**
- Completely free
- Easy setup
- Works with GitHub repos

**Cons:**
- No server-side features
- Requires GitHub repo

**Steps:**
1. Install gh-pages: `npm install --save-dev gh-pages`
2. Add to package.json scripts:
   ```json
   "homepage": "https://yourusername.github.io/prompt-wrapper",
   "predeploy": "npm run build",
   "deploy": "gh-pages -d build"
   ```
3. Run: `npm run deploy`
4. Enable GitHub Pages in repo settings

**Cost:** Free

---

### 4. **AWS Amplify** (Enterprise Option)
**Best for:** AWS ecosystem, enterprise needs

**Pros:**
- Full AWS integration
- Scalable
- CI/CD built-in
- Custom domains

**Cost:** Pay-as-you-go, ~$1-5/month for small apps

---

### 5. **Firebase Hosting** (Google Cloud)
**Best for:** Google ecosystem, real-time features

**Pros:**
- Free tier (10GB storage, 360MB/day transfer)
- Fast CDN
- Easy custom domains
- Integrates with Firebase services

**Cost:** Free tier available, then pay-as-you-go

---

## Quick Start: Vercel Deployment

### Option A: Deploy via Git (Recommended)

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/prompt-wrapper.git
   git push -u origin main
   ```

2. **Deploy on Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Sign up with GitHub
   - Click "New Project"
   - Import your repository
   - Click "Deploy" (no config needed!)

### Option B: Deploy via CLI

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Deploy:**
   ```bash
   cd prompt-wrapper
   vercel
   ```

3. **Follow the prompts** - it will auto-detect your settings

---

## Build for Production

Before deploying, test your production build locally:

```bash
# Build the app
npm run build

# Test the production build (optional)
npx serve -s build
```

The `build` folder contains your production-ready static files.

---

## Environment Variables

If you need environment variables:

1. **Create `.env` file** (for local development):
   ```
   REACT_APP_API_URL=https://api.example.com
   ```

2. **Add to hosting platform:**
   - Vercel: Project Settings → Environment Variables
   - Netlify: Site Settings → Build & Deploy → Environment Variables

**Note:** All React env vars must start with `REACT_APP_`

---

## Custom Domain Setup

### Vercel:
1. Go to Project Settings → Domains
2. Add your domain
3. Update DNS records as instructed

### Netlify:
1. Go to Site Settings → Domain Management
2. Add custom domain
3. Follow DNS setup instructions

---

## Performance Tips

1. **Enable compression** (automatic on Vercel/Netlify)
2. **Optimize images** before uploading
3. **Use lazy loading** for components
4. **Enable caching** (automatic on most platforms)

---

## Recommendation

**For your use case, I recommend Vercel** because:
- ✅ Easiest setup (2 minutes)
- ✅ Free tier is generous
- ✅ Automatic HTTPS and CDN
- ✅ Great for React apps
- ✅ Preview deployments for testing

Just push to GitHub and connect to Vercel - that's it!

