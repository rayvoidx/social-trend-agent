// ***********************************************************
// This support file is processed and loaded automatically before test files.
// ***********************************************************

// Import commands.js using ES2015 syntax:
import './commands'

// Alternatively you can use CommonJS syntax:
// require('./commands')

// Hide fetch/XHR in command log
const app = window.top;

if (app && !app.document.head.querySelector('[data-hide-command-log-request]')) {
  const style = app.document.createElement('style');
  style.innerHTML = '.command-name-request, .command-name-xhr { display: none }';
  style.setAttribute('data-hide-command-log-request', '');
  app.document.head.appendChild(style);
}

// Example: Add custom Cypress commands
declare global {
  namespace Cypress {
    interface Chainable {
      /**
       * Custom command to wait for API request to complete
       * @example cy.waitForAPI('/api/insights')
       */
      waitForAPI(url: string): Chainable<void>
    }
  }
}

export {}
