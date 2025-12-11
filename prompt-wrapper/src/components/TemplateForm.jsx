import React, { useState } from 'react';
import './TemplateForm.css';

const TemplateForm = ({ template, onSubmit, onBack }) => {
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});

  const handleChange = (fieldId, value) => {
    setFormData(prev => ({
      ...prev,
      [fieldId]: value
    }));
    // Clear error when user starts typing
    if (errors[fieldId]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldId];
        return newErrors;
      });
    }
  };

  const validateForm = () => {
    const newErrors = {};
    template.fields.forEach(field => {
      if (field.required && !formData[field.id]) {
        newErrors[field.id] = `${field.label} is required`;
      }
    });
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm()) {
      onSubmit(formData);
    }
  };

  const renderField = (field) => {
    const value = formData[field.id] || '';
    const hasError = errors[field.id];

    if (field.type === 'dropdown') {
      return (
        <div key={field.id} className="form-field">
          <label htmlFor={field.id}>
            {field.label}
            {field.required && <span className="required">*</span>}
          </label>
          <select
            id={field.id}
            value={value}
            onChange={(e) => handleChange(field.id, e.target.value)}
            className={hasError ? 'error' : ''}
          >
            <option value="">Select {field.label}</option>
            {field.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {hasError && <span className="error-message">{errors[field.id]}</span>}
        </div>
      );
    } else {
      return (
        <div key={field.id} className="form-field">
          <label htmlFor={field.id}>
            {field.label}
            {field.required && <span className="required">*</span>}
          </label>
          <input
            id={field.id}
            type="text"
            value={value}
            onChange={(e) => handleChange(field.id, e.target.value)}
            placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
            className={hasError ? 'error' : ''}
          />
          {hasError && <span className="error-message">{errors[field.id]}</span>}
        </div>
      );
    }
  };

  return (
    <div className="template-form-container">
      <div className="form-header">
        <button onClick={onBack} className="back-button">
          ← Back to Templates
        </button>
        <h2>{template.name}</h2>
        <p className="form-description">{template.description}</p>
      </div>
      
      <form onSubmit={handleSubmit} className="template-form">
        {template.fields.map(renderField)}
        
        <div className="form-actions">
          <button type="button" onClick={onBack} className="btn-secondary">
            Cancel
          </button>
          <button type="submit" className="btn-primary">
            Generate Prompt
          </button>
        </div>
      </form>
    </div>
  );
};

export default TemplateForm;


