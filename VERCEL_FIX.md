# Fix Vercel Build Error for Node 20+

## Quick Fix Steps

### Option 1: Upgrade to React Scripts 5.x (Recommended)

1. **Update `package.json`:**
   ```json
   {
     "engines": {
       "node": "20.x"
     },
     "dependencies": {
       "react": "^18.2.0",
       "react-dom": "^18.2.0",
       "react-scripts": "5.0.1"
     }
   }
   ```

2. **Update `src/index.js` to use React 18:**
   ```javascript
   import React from 'react';
   import ReactDOM from 'react-dom/client';
   import App from './App';
   import './index.css';

   const root = ReactDOM.createRoot(document.getElementById('root'));
   root.render(
     <React.StrictMode>
       <App />
     </React.StrictMode>
   );
   ```

3. **Install and test:**
   ```bash
   npm install
   npm run build
   ```

4. **Commit and push:**
   ```bash
   git add package.json src/index.js
   git commit -m "Upgrade to Node 20 and react-scripts 5"
   git push
   ```

### Option 2: Use NODE_OPTIONS Workaround

1. **Create `vercel.json` in project root:**
   ```json
   {
     "buildCommand": "NODE_OPTIONS=--openssl-legacy-provider npm run build",
     "framework": "create-react-app"
   }
   ```

2. **OR set environment variable in Vercel:**
   - Go to Project Settings → Environment Variables
   - Add: `NODE_OPTIONS` = `--openssl-legacy-provider`
   - Redeploy

### Option 3: Switch to Vite (Modern Alternative)

If you want a more modern setup:

1. **Install Vite:**
   ```bash
   npm install --save-dev vite @vitejs/plugin-react
   ```

2. **Update package.json:**
   ```json
   {
     "scripts": {
       "dev": "vite",
       "build": "vite build",
       "preview": "vite preview"
     }
   }
   ```

3. **Create `vite.config.js`:**
   ```javascript
   import { defineConfig } from 'vite'
   import react from '@vitejs/plugin-react'

   export default defineConfig({
     plugins: [react()],
   })
   ```

## Recommended: Use Option 1

React Scripts 5.x is fully compatible with Node 20+ and is the cleanest solution.


