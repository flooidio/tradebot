import React from 'react';
import './TemplateSelector.css';

const TemplateSelector = ({ templates, selectedTemplate, onSelectTemplate }) => {
  return (
    <div className="template-selector">
      <h2>Select a Template</h2>
      <p className="subtitle">Choose a prompt engineering template to get started</p>
      <div className="template-grid">
        {templates.map((template) => (
          <div
            key={template.id}
            className={`template-card ${selectedTemplate?.id === template.id ? 'selected' : ''}`}
            onClick={() => onSelectTemplate(template)}
          >
            <h3>{template.name}</h3>
            <p>{template.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TemplateSelector;


