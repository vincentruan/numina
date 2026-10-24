import type { ContentSection } from '../contentTypes'

export const privacyContent: ContentSection[] = [
  {
    heading: '1. Overview',
    blocks: [
      {
        type: 'paragraph',
        text: 'Numina ("we," "our," or "the System") is a privacy-first, self-hosted family asset visualization and management system released under the AGPL-3.0 open-source license. We recognize the sensitivity of financial data and have designed the system with privacy protection as a foundational principle.',
      },
      {
        type: 'paragraph',
        text: 'This Privacy Policy explains what information we collect, why we collect it, how we use it, and how we safeguard it. Please read this policy carefully and ensure you understand its contents.',
      },
      {
        type: 'paragraph',
        text: 'Deployment model: The System currently operates in self-hosted mode — you deploy and operate the server on your own infrastructure, and all data resides exclusively within your environment. The Numina development team has no access to your data whatsoever. We may offer a cloud-based SaaS service in the future, in which case this policy will be updated accordingly to address the hosted scenario.',
      },
    ],
  },
  {
    heading: '2. Information We Collect',
    blocks: [
      {
        type: 'paragraph',
        text: '2.1 Information You Provide',
      },
      {
        type: 'list',
        items: [
          'Registration data: a username and password (the server stores only a cryptographic hash of your password; plaintext passwords are never retained).',
          'Family group data: member relationship information you supply when creating or joining a family group, along with your assigned role (administrator or member).',
          'Financial data: assets, liabilities, transaction records, and account balances that you manually enter. All financial data is provided at your sole discretion — the System does not automatically access your real-world financial accounts.',
          'Family member data: names and roles you assign to family members, including children added by guardians.',
        ],
      },
      {
        type: 'paragraph',
        text: '2.2 Information Collected Automatically',
      },
      {
        type: 'list',
        items: [
          'Behavioral analytics: page views, feature usage frequency, and interaction patterns. This data contains no personally identifiable information (PII) and is used solely for product improvement.',
          'Error reports: when the application encounters an error, the System captures stack traces, device information (device model, operating system version), and browser version to facilitate diagnosis and remediation.',
          'Local storage data: your browser\'s localStorage stores your theme preference (light/dark mode), language setting, and authentication token.',
        ],
      },
      {
        type: 'paragraph',
        text: '2.3 Information We Do Not Collect',
      },
      {
        type: 'list',
        items: [
          'Biometric data (fingerprints, facial recognition, etc.).',
          'Health or medical information.',
          'Third-party advertising tracking data or advertising identifiers.',
          'Precise geolocation data.',
          'Contacts or SMS records.',
        ],
      },
    ],
  },
  {
    heading: '3. How We Use Information',
    blocks: [
      {
        type: 'paragraph',
        text: '3.1 Core Functionality',
      },
      {
        type: 'paragraph',
        text: 'We use the information you provide to deliver the System\'s core features, including but not limited to: authentication and authorization, family group management with role-based access control, asset and liability visualization, and financial report generation and data analysis.',
      },
      {
        type: 'paragraph',
        text: '3.2 AI Features and Data Processing',
      },
      {
        type: 'paragraph',
        text: 'The System offers optional AI-powered features. When you choose to enable these features, portions of your data are transmitted to third-party AI service providers for processing. We implement strict de-identification measures throughout this pipeline:',
      },
      {
        type: 'list',
        items: [
          'De-identification: before any data leaves your environment, user identifiers (user IDs, usernames) are stripped, and absolute monetary amounts are converted to relative ratios (e.g., percentage distributions) wherever possible to minimize data sensitivity.',
          'AI orchestration layer: LangChain and LangGraph serve as the orchestration framework for coordinating AI task execution across multiple services.',
          'Web search: Tavily provides web search capabilities to support the retrieval of real-time information by the AI.',
          'Code sandbox: e2b provides a secure code execution environment for data processing and computational tasks.',
          'Data minimization: only the minimum data necessary to complete a specific AI task is transmitted.',
        ],
      },
      {
        type: 'paragraph',
        text: 'Please note that despite our de-identification efforts, once data is transmitted to third-party service providers, it becomes subject to their respective privacy policies. We encourage you to review the privacy practices of these providers before enabling AI features.',
      },
      {
        type: 'paragraph',
        text: '3.3 Behavioral Analytics',
      },
      {
        type: 'paragraph',
        text: 'Behavioral analytics data (page views, feature usage, interaction patterns) is used exclusively to: assess feature adoption and usage to guide product development, identify pain points and opportunities for user experience improvement, and optimize system performance and responsiveness. This data contains no personally identifiable information.',
      },
      {
        type: 'paragraph',
        text: '3.4 Error Reporting',
      },
      {
        type: 'paragraph',
        text: 'Stack traces, device information, and browser version data captured in error reports are used solely for diagnosing and resolving software defects. We do not use error report data for any other purpose.',
      },
    ],
  },
  {
    heading: '4. Data Storage and Security',
    blocks: [
      {
        type: 'paragraph',
        text: '4.1 Data Storage in Self-Hosted Mode',
      },
      {
        type: 'paragraph',
        text: 'Under self-hosted deployment, all data — including user accounts, financial records, and AI conversation logs — resides on servers and databases that you manage and control exclusively. The Numina development team has no access of any kind to your data and cannot read, modify, or delete any of your information.',
      },
      {
        type: 'paragraph',
        text: 'As the operator of a self-hosted instance, you are responsible for implementing appropriate security measures to protect your data, including but not limited to: configuring firewalls and access controls, performing regular backups, and applying system and security patches in a timely manner.',
      },
      {
        type: 'paragraph',
        text: '4.2 Data Security in Future SaaS Mode',
      },
      {
        type: 'paragraph',
        text: 'Should we offer a cloud-based SaaS service in the future, we will implement the following security measures to protect your data:',
      },
      {
        type: 'list',
        items: [
          'Encryption in transit: all client-to-server communications will be encrypted via TLS/HTTPS.',
          'Encryption at rest: sensitive data stored in databases will be encrypted using industry-standard algorithms.',
          'Access controls: strict authentication and authorization mechanisms will ensure that only authorized personnel can access data.',
          'Security auditing: regular security audits and penetration testing will be conducted to identify and remediate potential vulnerabilities.',
        ],
      },
    ],
  },
  {
    heading: '5. Third-Party Data Sharing',
    blocks: [
      {
        type: 'paragraph',
        text: '5.1 AI Service Providers',
      },
      {
        type: 'paragraph',
        text: 'When you enable AI features, de-identified data is shared with the following third-party service providers:',
      },
      {
        type: 'list',
        items: [
          'LangChain / LangGraph: as the AI orchestration framework, these services receive de-identified task context data to coordinate AI task execution.',
          'Tavily: provides web search capabilities and receives de-identified search queries.',
          'e2b: provides a secure code execution sandbox environment and receives de-identified computational task data.',
          'Large Language Model (LLM) providers: depending on your configured AI model, your de-identified data is sent to the corresponding LLM service provider (e.g., Anthropic, OpenAI, or others) for inference processing.',
        ],
      },
      {
        type: 'paragraph',
        text: 'Specific de-identification measures include: stripping user identifiers (user IDs, usernames, etc.), converting absolute monetary amounts to relative ratios (e.g., asset distribution percentages), and removing information that could directly identify an individual or family. Please be aware, however, that de-identification is not equivalent to anonymization — in certain circumstances, data may still be re-associated with identifiable individuals.',
      },
      {
        type: 'paragraph',
        text: '5.2 Error Reporting Services',
      },
      {
        type: 'paragraph',
        text: 'Error report data may contain stack traces, device model, operating system version, and browser version — all technical in nature. This information is used exclusively to diagnose and fix software defects and does not include your financial data or any personally identifiable information.',
      },
      {
        type: 'paragraph',
        text: '5.3 Other Circumstances',
      },
      {
        type: 'paragraph',
        text: 'Beyond the scenarios described above, we do not share your information with any third party unless: you provide explicit consent, disclosure is required by applicable law or judicial order, or disclosure is reasonably necessary to protect the safety, rights, or property of the System or its users.',
      },
    ],
  },
  {
    heading: '6. Data Retention and Deletion',
    blocks: [
      {
        type: 'paragraph',
        text: 'Self-hosted mode: You retain full control over data retention periods. You may delete any data at any time by directly managing your database, or purge all data by removing your entire database instance.',
      },
      {
        type: 'paragraph',
        text: 'AI-related data: data transmitted to third-party AI service providers after de-identification is subject to the data retention policies of each respective provider. We recommend reviewing the privacy policies of these providers to understand their data retention practices.',
      },
      {
        type: 'paragraph',
        text: 'Future SaaS mode: should we offer a cloud-based service, upon account deletion we will remove all your personal data within a reasonable period (typically no longer than 30 days), except where retention is required by applicable law.',
      },
    ],
  },
  {
    heading: '7. Your Rights',
    blocks: [
      {
        type: 'paragraph',
        text: 'You have the following rights with respect to your data:',
      },
      {
        type: 'list',
        items: [
          'Right of access: you may view and export all financial data and personal information stored in the System.',
          'Right of rectification: you may modify and correct inaccurate personal information and financial data within the System.',
          'Right of erasure: you may delete any data within the System. In self-hosted mode, this is accomplished through direct database management; in future SaaS mode, this will be available through account settings or by contacting the operator.',
          'Right to data portability: you may export your data in a commonly used format for migration to other systems.',
          'Right to withdraw consent: you may disable AI features at any time in System settings to cease transmitting data to third-party AI service providers.',
        ],
      },
      {
        type: 'paragraph',
        text: 'In self-hosted mode, the exercise of these rights is achieved primarily through your direct administration of your own server. If you need to exercise these rights under a future SaaS deployment, please contact us using the details provided at the end of this policy.',
      },
    ],
  },
  {
    heading: '8. Children\'s Privacy',
    blocks: [
      {
        type: 'paragraph',
        text: 'The System permits guardians (family group administrators) to add children as family members. Children\'s data is processed in the same manner as that of adult members.',
      },
      {
        type: 'paragraph',
        text: 'As a guardian, you are responsible for supervising children\'s activity within the System and for ensuring the security of their data. We recommend periodically reviewing the member list and role settings within your family group.',
      },
      {
        type: 'paragraph',
        text: 'When AI features are enabled, data related to children undergoes the same de-identification process described above. If you do not wish for children\'s data to be transmitted to third-party AI services, please refrain from enabling AI features for family groups that include child members.',
      },
      {
        type: 'paragraph',
        text: 'Should we offer a SaaS service in the future that knowingly collects personal information from children under 13, we will comply with applicable children\'s privacy protection laws and regulations (including COPPA and relevant provisions of the Personal Information Protection Law regarding minors) and will obtain verifiable parental consent prior to collection.',
      },
    ],
  },
  {
    heading: '9. Cookies and Local Storage',
    blocks: [
      {
        type: 'paragraph',
        text: 'The System does not currently use third-party tracking cookies.',
      },
      {
        type: 'paragraph',
        text: 'The System uses browser localStorage to store the following information to maintain your user experience:',
      },
      {
        type: 'list',
        items: [
          'Theme preference (light mode / dark mode).',
          'Language setting (Chinese / English).',
          'Authentication token (auth token) to maintain your logged-in session.',
        ],
      },
      {
        type: 'paragraph',
        text: 'All of the above local storage data resides exclusively on your device and is never transmitted to the server or any third party. You may clear localStorage data at any time through your browser\'s privacy settings; however, clearing this data will invalidate your login session and require you to log in again.',
      },
      {
        type: 'paragraph',
        text: 'In the future, we may introduce third-party analytics services (e.g., Google Analytics). Should this occur, we will update this policy accordingly and obtain your consent through an in-app prompt before implementation.',
      },
    ],
  },
  {
    heading: '10. Policy Updates',
    blocks: [
      {
        type: 'paragraph',
        text: 'We may update this Privacy Policy from time to time. Updates may include: new data processing scenarios (such as the introduction of SaaS services or new AI feature providers), reflection of changes in applicable laws and regulations, and clarification or strengthening of existing provisions.',
      },
      {
        type: 'paragraph',
        text: 'Material changes will be communicated to you through: in-app notifications or prompts, and updates to the "Last updated" date on this policy page.',
      },
      {
        type: 'paragraph',
        text: 'We recommend reviewing the latest version of this policy each time you use the System to stay informed about how we protect your information.',
      },
    ],
  },
  {
    heading: '11. Contact Us',
    blocks: [
      {
        type: 'paragraph',
        text: 'If you have any questions, comments, or suggestions regarding this Privacy Policy, or if you wish to exercise any of the rights described above, please contact us through the following channels:',
      },
      {
        type: 'list',
        items: [
          'Project repository: https://github.com/vincentruan/numina',
          'Submit your questions or feedback via the Issues feature in the project repository.',
        ],
      },
      {
        type: 'paragraph',
        text: 'We will respond to your inquiry as promptly as possible and address your request within a reasonable timeframe.',
      },
    ],
  },
]
