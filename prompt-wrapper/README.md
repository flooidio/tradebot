# Prompt Engineering Wrapper

A React application that serves as a wrapper for sending prompts with best practices in prompt engineering. The interface allows users to select from common prompt templates and fill in fields to create optimized prompts.

## Features

- **Template Selection**: Choose from common prompt engineering templates including:
  - Data Analysis
  - Content Creation
  - Problem Solving
  - Decision Support
  - Summarization
  - Code Generation

- **Dynamic Forms**: Each template presents a form with:
  - Dropdown fields for predefined options
  - Text input fields for custom content
  - Required field validation

- **Prompt Generation**: Automatically generates structured prompts based on selected template and filled fields

## Getting Started

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn

### Installation

1. Navigate to the prompt-wrapper directory:
```bash
cd prompt-wrapper
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

4. Open your browser and navigate to `http://localhost:3000`

### Building for Production

```bash
npm run build
```

The built files will be in the `build` directory.

## Project Structure

```
prompt-wrapper/
├── public/
│   └── index.html                  # HTML template
├── src/
│   ├── components/
│   │   ├── TemplateSelector.jsx    # Template selection component
│   │   ├── TemplateSelector.css
│   │   ├── TemplateForm.jsx        # Dynamic form component
│   │   └── TemplateForm.css
│   ├── templates.js                # Template definitions
│   ├── App.jsx                     # Main app component
│   ├── App.css
│   ├── index.js                    # Entry point
│   └── index.css                   # Global styles
├── package.json
└── README.md
```

## Usage

1. **Select a Template**: Click on one of the template cards to choose a prompt type
2. **Fill in Fields**: Complete the form with the required information
   - Dropdown fields: Select from predefined options
   - Text fields: Enter custom information
3. **Generate Prompt**: Click "Generate Prompt" to create your structured prompt
4. **Copy Prompt**: Use the "Copy to Clipboard" button to copy the generated prompt

## Deployment

This app is ready for production deployment. See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed hosting options.

### Quick Deploy to Vercel (Recommended)

1. Push your code to GitHub
2. Go to [vercel.com](https://vercel.com) and sign up
3. Import your repository
4. Click "Deploy" - done!

### Build for Production

```bash
npm run build
```

This creates a `build` folder with optimized production files.

## Future Enhancements

- RAG (Retrieval-Augmented Generation) integration for context-specific queries
- Custom template creation
- Prompt history and saving
- Integration with AI APIs
- Export options (JSON, PDF, etc.)


