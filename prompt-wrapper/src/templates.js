// Common prompt engineering templates
export const templates = [
  {
    id: 'analysis',
    name: 'Data Analysis',
    description: 'Analyze data and extract insights',
    fields: [
      {
        id: 'data_type',
        label: 'Data Type',
        type: 'dropdown',
        options: ['Sales Data', 'Customer Feedback', 'Financial Metrics', 'Market Research', 'Other'],
        required: true
      },
      {
        id: 'analysis_goal',
        label: 'Analysis Goal',
        type: 'text',
        placeholder: 'What insights are you looking for?',
        required: true
      },
      {
        id: 'timeframe',
        label: 'Timeframe',
        type: 'dropdown',
        options: ['Last Week', 'Last Month', 'Last Quarter', 'Last Year', 'All Time'],
        required: false
      },
      {
        id: 'specific_metrics',
        label: 'Specific Metrics to Focus On',
        type: 'text',
        placeholder: 'e.g., conversion rate, revenue, customer satisfaction',
        required: false
      }
    ]
  },
  {
    id: 'content_creation',
    name: 'Content Creation',
    description: 'Generate content for marketing, documentation, or communication',
    fields: [
      {
        id: 'content_type',
        label: 'Content Type',
        type: 'dropdown',
        options: ['Blog Post', 'Email', 'Social Media', 'Product Description', 'Documentation', 'Press Release'],
        required: true
      },
      {
        id: 'topic',
        label: 'Topic',
        type: 'text',
        placeholder: 'What is the main topic?',
        required: true
      },
      {
        id: 'tone',
        label: 'Tone',
        type: 'dropdown',
        options: ['Professional', 'Casual', 'Friendly', 'Formal', 'Technical', 'Creative'],
        required: true
      },
      {
        id: 'target_audience',
        label: 'Target Audience',
        type: 'text',
        placeholder: 'Who is the target audience?',
        required: false
      },
      {
        id: 'length',
        label: 'Approximate Length',
        type: 'dropdown',
        options: ['Short (100-300 words)', 'Medium (300-800 words)', 'Long (800+ words)'],
        required: false
      }
    ]
  },
  {
    id: 'problem_solving',
    name: 'Problem Solving',
    description: 'Analyze problems and propose solutions',
    fields: [
      {
        id: 'problem_category',
        label: 'Problem Category',
        type: 'dropdown',
        options: ['Technical', 'Business Process', 'Customer Service', 'Product', 'Strategic', 'Operational'],
        required: true
      },
      {
        id: 'problem_description',
        label: 'Problem Description',
        type: 'text',
        placeholder: 'Describe the problem in detail',
        required: true
      },
      {
        id: 'constraints',
        label: 'Constraints',
        type: 'text',
        placeholder: 'Budget, time, resources, or other limitations',
        required: false
      },
      {
        id: 'success_criteria',
        label: 'Success Criteria',
        type: 'text',
        placeholder: 'How will you measure success?',
        required: false
      }
    ]
  },
  {
    id: 'decision_support',
    name: 'Decision Support',
    description: 'Get structured analysis to support decision-making',
    fields: [
      {
        id: 'decision_type',
        label: 'Decision Type',
        type: 'dropdown',
        options: ['Strategic', 'Tactical', 'Operational', 'Investment', 'Hiring', 'Partnership'],
        required: true
      },
      {
        id: 'decision_context',
        label: 'Decision Context',
        type: 'text',
        placeholder: 'What decision needs to be made?',
        required: true
      },
      {
        id: 'options',
        label: 'Options to Consider',
        type: 'text',
        placeholder: 'List the options or alternatives',
        required: false
      },
      {
        id: 'evaluation_criteria',
        label: 'Evaluation Criteria',
        type: 'text',
        placeholder: 'What factors should be considered?',
        required: false
      }
    ]
  },
  {
    id: 'summarization',
    name: 'Summarization',
    description: 'Summarize documents, meetings, or information',
    fields: [
      {
        id: 'source_type',
        label: 'Source Type',
        type: 'dropdown',
        options: ['Document', 'Meeting Notes', 'Research Paper', 'Article', 'Report', 'Conversation'],
        required: true
      },
      {
        id: 'summary_length',
        label: 'Summary Length',
        type: 'dropdown',
        options: ['Brief (1-2 paragraphs)', 'Medium (3-5 paragraphs)', 'Detailed (5+ paragraphs)'],
        required: true
      },
      {
        id: 'key_points',
        label: 'Key Points to Include',
        type: 'text',
        placeholder: 'Specific topics or themes to emphasize',
        required: false
      },
      {
        id: 'audience',
        label: 'Target Audience',
        type: 'text',
        placeholder: 'Who will read this summary?',
        required: false
      }
    ]
  },
  {
    id: 'code_generation',
    name: 'Code Generation',
    description: 'Generate code with specifications',
    fields: [
      {
        id: 'programming_language',
        label: 'Programming Language',
        type: 'dropdown',
        options: ['Python', 'JavaScript', 'TypeScript', 'Java', 'C++', 'Go', 'Rust', 'Other'],
        required: true
      },
      {
        id: 'task_description',
        label: 'Task Description',
        type: 'text',
        placeholder: 'What should the code do?',
        required: true
      },
      {
        id: 'framework',
        label: 'Framework/Library',
        type: 'text',
        placeholder: 'e.g., React, Django, Express',
        required: false
      },
      {
        id: 'requirements',
        label: 'Specific Requirements',
        type: 'text',
        placeholder: 'Performance, security, or other requirements',
        required: false
      }
    ]
  }
];


