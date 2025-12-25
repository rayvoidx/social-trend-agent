/// <reference types="cypress" />

// ***********************************************
// Custom Cypress commands
// ***********************************************

/**
 * Wait for API request to complete
 */
Cypress.Commands.add('waitForAPI', (url: string) => {
  cy.intercept('GET', url).as('apiRequest')
  cy.wait('@apiRequest')
})

// Prevent TypeScript errors
export {}
