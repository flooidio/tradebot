import React, { useState } from 'react';
import TemplateSelector from './components/TemplateSelector';
import TemplateForm from './components/TemplateForm';
import { templates } from './templates';
import './App.css';

function App() {
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [generatedPrompt, setGeneratedPrompt] = useState(null);

  const handleSelectTemplate = (template) => {
    setSelectedTemplate(template);
    setGeneratedPrompt(null);
  };

  const handleBack = () => {
    setSelectedTemplate(null);
    setGeneratedPrompt(null);
  };

  const handleSubmit = (formData) => {
    // Generate the prompt based on template and form data
    const prompt = generatePrompt(selectedTemplate, formData);
    setGeneratedPrompt(prompt);
  };

  const generatePrompt = (template, formData) => {
    // Build a structured prompt based on the template and filled fields
    let prompt = `# ${template.name}\n\n`;
    prompt += `${template.description}\n\n`;
    
    prompt += `## Context:\n`;
    template.fields.forEach(field => {
      if (formData[field.id]) {
        prompt += `- **${field.label}**: ${formData[field.id]}\n`;
      }
    });
    
    prompt += `\n## Instructions:\n`;
    prompt += `Please provide a comprehensive response based on the above context and following best practices in prompt engineering:\n`;
    prompt += `1. Be specific and clear in your response\n`;
    prompt += `2. Consider all provided context and requirements\n`;
    prompt += `3. Structure your response appropriately\n`;
    prompt += `4. Provide actionable insights or solutions\n`;
    
    return prompt;
  };

  return (
    <div className="app">
      <div className="app-container">
        <header className="app-header">
          <h1>Prompt Engineering Wrapper</h1>
          <p>Select templates and fill in fields to create optimized prompts</p>
        </header>

        {!selectedTemplate ? (
          <TemplateSelector
            templates={templates}
            selectedTemplate={selectedTemplate}
            onSelectTemplate={handleSelectTemplate}
          />
        ) : (
          <>
            <TemplateForm
              template={selectedTemplate}
              onSubmit={handleSubmit}
              onBack={handleBack}
            />
            {generatedPrompt && (
              <div className="prompt-output">
                <h3>Generated Prompt</h3>
                <div className="prompt-content">
                  <pre>{generatedPrompt}</pre>
                </div>
                <div className="prompt-actions">
                  <button
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(generatedPrompt);
                        alert('Prompt copied to clipboard!');
                      } catch (err) {
                        console.error('Failed to copy:', err);
                        // Fallback: select text for manual copy
                        const textArea = document.createElement('textarea');
                        textArea.value = generatedPrompt;
                        document.body.appendChild(textArea);
                        textArea.select();
                        try {
                          document.execCommand('copy');
                          alert('Prompt copied to clipboard!');
                        } catch (fallbackErr) {
                          alert('Failed to copy. Please select and copy manually.');
                        }
                        document.body.removeChild(textArea);
                      }
                    }}
                    className="btn-primary"
                  >
                    Copy to Clipboard
                  </button>
                  <button
                    onClick={() => setGeneratedPrompt(null)}
                    className="btn-secondary"
                  >
                    Clear
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default App;

