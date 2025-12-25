/**
 * E2E tests for the main dashboard
 */

describe('Dashboard E2E Tests', () => {
  beforeEach(() => {
    // Visit the dashboard before each test
    cy.visit('/')
  })

  it('should load the dashboard page', () => {
    // Check that the page loads
    cy.contains('Social Trend Agent').should('be.visible')
  })

  it('should display the header', () => {
    // Verify header is present
    cy.get('header').should('exist')
  })

  it('should render the analysis form', () => {
    // Check for form elements
    cy.get('form').should('exist')

    // Check for query input
    cy.get('input[type="text"]').should('exist')

    // Check for submit button
    cy.get('button[type="submit"]').should('exist')
  })

  it('should submit a query and show results', () => {
    // Intercept API call
    cy.intercept('POST', '/api/tasks', {
      statusCode: 200,
      body: {
        task_id: 'test-task-123',
        status: 'submitted',
        message: 'Task submitted successfully'
      }
    }).as('submitTask')

    // Fill in the form
    cy.get('input[type="text"]').type('AI trends 2025')

    // Submit
    cy.get('button[type="submit"]').click()

    // Wait for API call
    cy.wait('@submitTask')

    // Verify success message or loading state
    cy.contains(/submitt|success|loading/i, { timeout: 10000 }).should('exist')
  })

  it('should navigate between different sections', () => {
    // Test navigation if there are tabs/sections
    cy.get('[role="tab"]').first().click()

    // Verify active state
    cy.get('[role="tab"][aria-selected="true"]').should('exist')
  })

  it('should be responsive on mobile', () => {
    // Test mobile viewport
    cy.viewport('iphone-x')

    // Verify layout adjusts
    cy.get('header').should('be.visible')
    cy.get('main').should('be.visible')
  })

  it('should display error message on API failure', () => {
    // Intercept API call with error
    cy.intercept('POST', '/api/tasks', {
      statusCode: 500,
      body: { error: 'Internal server error' }
    }).as('submitTaskError')

    // Fill and submit form
    cy.get('input[type="text"]').type('test query')
    cy.get('button[type="submit"]').click()

    // Wait for API call
    cy.wait('@submitTaskError')

    // Verify error message
    cy.contains(/error|fail/i, { timeout: 10000 }).should('exist')
  })

  it('should fetch and display insights list', () => {
    // Intercept insights API
    cy.intercept('GET', '/api/insights*', {
      statusCode: 200,
      body: {
        total: 2,
        items: [
          {
            id: '1',
            source: 'news_trend_agent',
            query: 'AI trends',
            created_at: Date.now() / 1000
          },
          {
            id: '2',
            source: 'viral_video_agent',
            query: 'TikTok trends',
            created_at: Date.now() / 1000
          }
        ]
      }
    }).as('getInsights')

    // Trigger insights fetch (might be on page load or button click)
    cy.visit('/')

    // Wait for insights
    cy.wait('@getInsights')

    // Verify insights are displayed
    cy.contains('AI trends').should('exist')
    cy.contains('TikTok trends').should('exist')
  })
})

describe('Dashboard Accessibility', () => {
  beforeEach(() => {
    cy.visit('/')
  })

  it('should have proper heading structure', () => {
    cy.get('h1').should('have.length.at.least', 1)
  })

  it('should have accessible form inputs', () => {
    cy.get('input[type="text"]').should('have.attr', 'placeholder')
  })

  it('should support keyboard navigation', () => {
    // Tab through interactive elements
    cy.get('body').tab()
    cy.focused().should('exist')

    // Continue tabbing
    cy.focused().tab()
    cy.focused().should('exist')
  })
})
