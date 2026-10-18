import type { ContentSection } from '../contentTypes'

export const termsContent: ContentSection[] = [
  {
    heading: '1. Acceptance of Terms',
    blocks: [
      {
        type: 'paragraph',
        text: 'Welcome to Numina ("the Software"). These Terms of Service ("Terms") constitute a legally binding agreement between you and the Numina project governing your use of the Software.',
      },
      {
        type: 'paragraph',
        text: 'By registering an account, installing, copying, or otherwise accessing the Software, you acknowledge that you have read, understood, and agree to be bound by these Terms. If you do not agree to any part of these Terms, you must not use the Software.',
      },
      {
        type: 'paragraph',
        text: 'These Terms apply to all users of the Software, including account administrators, family member accounts, and any third parties interacting with the Software through APIs or other means.',
      },
    ],
  },
  {
    heading: '2. Description of Service',
    blocks: [
      {
        type: 'paragraph',
        text: 'Numina is a privacy-first, self-deployable family asset visualization and management system. The Software is designed to help families track, manage, and visualize their assets and liabilities, with support for multi-member collaboration and role-based access control.',
      },
      {
        type: 'paragraph',
        text: 'Core features of the Software include:',
      },
      {
        type: 'list',
        items: [
          'Recording, categorizing, querying, and visualizing family assets and liabilities;',
          'Multi-user account management and role-based permission control within family groups;',
          'Optional AI-assisted features, including asset analysis reports and intelligent financial suggestions;',
          'Data export and backup capabilities;',
          'Other ancillary functions related to family asset management.',
        ],
      },
      {
        type: 'paragraph',
        text: 'You acknowledge that the Software is self-deployed and self-maintained by you (see Section 4). The Numina project provides only the source code and does not directly provide hosting services unless otherwise stated in the future.',
      },
    ],
  },
  {
    heading: '3. Open Source License',
    blocks: [
      {
        type: 'paragraph',
        text: 'The Software is licensed under the GNU Affero General Public License version 3 (AGPL-3.0). Your use, reproduction, modification, and distribution of the Software are subject to the terms of the AGPL-3.0.',
      },
      {
        type: 'paragraph',
        text: 'Key obligations under the AGPL-3.0 include, but are not limited to:',
      },
      {
        type: 'list',
        items: [
          'If you modify the Software, you must release the modified source code under the AGPL-3.0;',
          'If you provide the Software (including modified versions) as a service over a network, you must make the complete source code available to users of that service;',
          'You must preserve all copyright notices and this license;',
          'You may not impose additional restrictive terms on the Software.',
        ],
      },
      {
        type: 'paragraph',
        text: 'These Terms do not modify or limit any rights you enjoy under the AGPL-3.0. For the full text of the AGPL-3.0, please refer to the Free Software Foundation\'s official website.',
      },
    ],
  },
  {
    heading: '4. Self-Deployment and Data Control',
    blocks: [
      {
        type: 'paragraph',
        text: 'The Software operates in a self-deployment model. You are responsible for installing, configuring, and maintaining the Software and its dependencies (including but not limited to PostgreSQL, Nginx, and the Docker container runtime) on servers of your own choosing.',
      },
      {
        type: 'paragraph',
        text: 'Under the self-deployment model:',
      },
      {
        type: 'list',
        items: [
          'You maintain full control over all data in your deployed instance, including account information, family group data, and asset and liability records;',
          'The Numina project does not collect, store, or access any user data in your instance unless you have explicitly enabled the telemetry features described in Section 8;',
          'You are responsible for ensuring that your deployment complies with applicable data protection laws and regulations (including but not limited to the EU General Data Protection Regulation and equivalent local legislation);',
          'You are responsible for implementing appropriate security measures, including data encryption, access controls, regular backups, and system updates.',
        ],
      },
      {
        type: 'paragraph',
        text: 'You acknowledge and agree that the Numina project shall not be liable for any data loss or service interruption resulting from improper deployment configuration, including but not limited to server security vulnerabilities, insufficient database backups, or network misconfigurations.',
      },
    ],
  },
  {
    heading: '5. Accounts and Family Groups',
    blocks: [
      {
        type: 'paragraph',
        text: 'Certain features of the Software require account registration. When registering, you agree to provide true, accurate, and complete personal information and to update such information promptly when it changes.',
      },
      {
        type: 'paragraph',
        text: 'The Software supports the creation of family groups with role-based access control among members. As the creator or administrator of a family group, you are responsible for:',
      },
      {
        type: 'list',
        items: [
          'Safeguarding your account credentials, including usernames, passwords, and any security tokens;',
          'Assuming full responsibility for all activities conducted through your account;',
          'Obtaining consent from family members before inviting them to join a family group;',
          'Reasonably assigning roles and permissions to family group members;',
          'Taking prompt remedial action upon discovering any unauthorized access to your account.',
        ],
      },
      {
        type: 'paragraph',
        text: 'You shall not share your login credentials with others or permit unauthorized persons to access the Software through your account. You bear sole responsibility for any data breach or loss resulting from credential sharing.',
      },
    ],
  },
  {
    heading: '6. User Content',
    blocks: [
      {
        type: 'paragraph',
        text: 'The Software allows you to record and manage financial data and other information related to family assets and liabilities (collectively, "User Content"). You retain all rights to the User Content you enter.',
      },
      {
        type: 'paragraph',
        text: 'You acknowledge and agree that:',
      },
      {
        type: 'list',
        items: [
          'You are solely responsible for your User Content; the Numina project assumes no liability for the accuracy, completeness, or legality of User Content;',
          'You shall ensure that your User Content does not infringe upon the lawful rights of any third party or contain prohibited information;',
          'In self-deployed instances, User Content is stored in databases under your control; the Numina project cannot access or delete such data;',
          'You should back up your User Content regularly to prevent data loss.',
        ],
      },
      {
        type: 'paragraph',
        text: 'If the Software is made available as a hosted SaaS service in the future (see Section 11), terms regarding the storage, migration, and deletion of User Content will be published separately at that time.',
      },
    ],
  },
  {
    heading: '7. AI-Powered Features',
    blocks: [
      {
        type: 'paragraph',
        text: 'The Software provides optional AI-assisted features, including but not limited to intelligent asset analysis reports, financial suggestions, and conversational assistants. These features are powered by third-party AI services using technology components including, but not limited to, LangChain, LangGraph, Tavily, and e2b.',
      },
      {
        type: 'paragraph',
        text: 'When using AI features, please note the following:',
      },
      {
        type: 'list',
        items: [
          'Your data will be de-identified before being transmitted to third-party AI service providers for processing. De-identification measures are designed to remove or replace information that can directly identify an individual;',
          'Notwithstanding de-identification measures, you should exercise caution in selecting what you input. Avoid entering directly identifiable sensitive information (such as national identification numbers or full bank card numbers) in AI conversations;',
          'Third-party AI service providers\' data processing practices are governed by their respective privacy policies. The Numina project has no control over the data handling practices of third-party providers;',
          'AI-generated content is provided for reference only and does not constitute professional financial, legal, or tax advice. You should consult qualified professionals for significant financial decisions;',
          'AI outputs may contain errors, omissions, or inaccuracies. You should independently verify the accuracy of AI outputs and assume full responsibility for their use.',
        ],
      },
      {
        type: 'paragraph',
        text: 'You may choose whether to enable AI features in the Software settings. Disabling AI features will not affect the normal operation of other functions of the Software.',
      },
    ],
  },
  {
    heading: '8. Analytics and Error Reporting',
    blocks: [
      {
        type: 'paragraph',
        text: 'To improve software quality and user experience, the Software may collect the following telemetry data:',
      },
      {
        type: 'list',
        items: [
          'Behavioral analytics: aggregated statistical data on page views, feature usage, and interaction patterns;',
          'Error reports: application crash information, exception stack traces, and system environment details at the time of errors.',
        ],
      },
      {
        type: 'paragraph',
        text: 'Principles governing telemetry data processing:',
      },
      {
        type: 'list',
        items: [
          'Telemetry data does not include asset details, liability records, or other substantive User Content;',
          'Under self-deployment, telemetry collection may be disabled or restricted through software configuration;',
          'Collected telemetry data is used solely for improving software functionality and fixing defects; it will not be sold or shared with third parties;',
          'Telemetry data processing complies with applicable data protection laws.',
        ],
      },
      {
        type: 'paragraph',
        text: 'By enabling telemetry in your self-deployed instance, you consent to the data collection described in this section. You may disable telemetry data collection at any time by modifying your deployment configuration.',
      },
    ],
  },
  {
    heading: '9. Disclaimer of Warranties',
    blocks: [
      {
        type: 'paragraph',
        text: 'THE SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.',
      },
      {
        type: 'paragraph',
        text: 'The Numina project does not warrant that:',
      },
      {
        type: 'list',
        items: [
          'The Software will meet your specific needs or expectations;',
          'The Software will operate uninterrupted, in a timely manner, securely, or without errors;',
          'Any information, advice, or reports obtained through the Software (including AI-generated content) are accurate, reliable, or complete;',
          'Any defects in the Software will be corrected in a timely manner.',
        ],
      },
      {
        type: 'paragraph',
        text: 'You acknowledge that managing family assets and liabilities through the Software involves significant financial decisions. The tools, analyses, and insights provided by the Software are for informational purposes only and should not serve as the sole basis for material financial decisions. You assume sole responsibility for your use of the Software.',
      },
      {
        type: 'paragraph',
        text: 'TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, ALL EXPRESS OR IMPLIED WARRANTIES, CONDITIONS, AND REPRESENTATIONS ARE EXCLUDED.',
      },
    ],
  },
  {
    heading: '10. Limitation of Liability',
    blocks: [
      {
        type: 'paragraph',
        text: 'TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE NUMINA PROJECT, ITS CONTRIBUTORS, AND MAINTAINERS SHALL NOT BE LIABLE FOR:',
      },
      {
        type: 'list',
        items: [
          'Any direct, indirect, incidental, special, consequential, or punitive damages arising from the use of or inability to use the Software, including but not limited to loss of profits, data loss, business interruption, or goodwill damage;',
          'Any losses resulting from your deployment environment, including but not limited to server failure, network interruption, or security breaches;',
          'Any losses caused by the unavailability, latency, or erroneous output of third-party AI services;',
          'Any consequences arising from your breach of these Terms or from inaccurate or improperly entered User Content.',
        ],
      },
      {
        type: 'paragraph',
        text: 'The foregoing limitation of liability applies to any claim based on contract, tort (including negligence), strict liability, or any other legal theory, even if the Numina project has been advised of the possibility of such damages.',
      },
      {
        type: 'paragraph',
        text: 'If applicable law does not permit the exclusion or limitation of the above liability, the liability of the Numina project shall be limited to the maximum extent permitted by law and shall not exceed the amount you actually paid for the use of the Software in the twelve (12) months preceding the event giving rise to the claim (if any).',
      },
    ],
  },
  {
    heading: '11. Future Service Changes',
    blocks: [
      {
        type: 'paragraph',
        text: 'The Numina project reserves the right to introduce a hosted service (SaaS) model in the future. If the Software expands or transitions to include hosted services, the following terms shall apply:',
      },
      {
        type: 'list',
        items: [
          'Hosted services will be subject to separately published terms of service and privacy policies, and you will receive adequate notice and the opportunity to opt in;',
          'Your existing self-deployed instance and the data stored therein shall not be bound by future hosted service terms unless you voluntarily migrate to the hosted service and expressly agree to the new terms;',
          'The core functionality of the Software will continue to be available as open source and will not be in violation of the AGPL-3.0 license;',
          'Hosted services may include additional paid features and billing terms, which will be disclosed to you at the time of subscription.',
        ],
      },
      {
        type: 'paragraph',
        text: 'The Numina project reserves the right to modify the Software\'s features, architecture, or availability at any time, including but not limited to adding, modifying, or removing functional modules, changing technology stack components, or adjusting performance parameters. For changes that do not affect the normal operation of your existing self-deployed instance, the Numina project has no obligation to provide prior notice.',
      },
    ],
  },
  {
    heading: '12. Modifications to Terms',
    blocks: [
      {
        type: 'paragraph',
        text: 'The Numina project reserves the right to modify these Terms at any time. Updated Terms will be published in the Software\'s code repository or within your deployed instance.',
      },
      {
        type: 'paragraph',
        text: 'For self-deployment users, modifications to these Terms will be reflected through Software version updates. Your continued use of the Software after modifications constitutes your acceptance of the updated Terms. If you do not agree to the updated Terms, you should cease using the Software.',
      },
      {
        type: 'paragraph',
        text: 'If hosted services are offered in the future, material changes to Terms that substantially affect your rights and obligations will be communicated in advance through in-app notifications, email, or other reasonable means.',
      },
      {
        type: 'paragraph',
        text: 'The latest version of these Terms, as published in the Software\'s code repository, shall prevail. In the event of any inconsistency between language versions, the Chinese version shall govern (unless otherwise required by applicable law).',
      },
    ],
  },
  {
    heading: '13. Contact Information',
    blocks: [
      {
        type: 'paragraph',
        text: 'If you have any questions, comments, or suggestions regarding these Terms, or if you believe that a deployed instance of the Software infringes upon your lawful rights, please contact us through the following channels:',
      },
      {
        type: 'list',
        items: [
          'Project repository: https://github.com/vincentruan/numina — submit an issue or contact us via GitHub;',
          'Email: Please use the contact information published in the project repository.',
        ],
      },
      {
        type: 'paragraph',
        text: 'We will respond to your correspondence within a reasonable time but assume no liability for any damages caused by delayed responses.',
      },
      {
        type: 'paragraph',
        text: 'These Terms were last updated: October 18, 2026.',
      },
    ],
  },
]
