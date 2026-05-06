/**
 * End-to-end tests for MindPilot knowledge base management.
 */
import { test, expect } from '@playwright/test'

test.describe('Knowledge Base Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/knowledge')
  })

  test('should display knowledge base list', async ({ page }) => {
    // Check page title
    await expect(page.locator('h1, h2')).toContainText(/知识库|Knowledge/i)

    // Check for create button
    await expect(page.locator('button:has-text("创建"), button:has-text("新建")')).toBeVisible()
  })

  test('should open create knowledge base dialog', async ({ page }) => {
    const createButton = page.locator('button:has-text("创建"), button:has-text("新建")').first()

    await createButton.click()

    // Dialog should appear
    await expect(page.locator('.el-dialog, .modal, [role="dialog"]')).toBeVisible()
  })

  test('should create a knowledge base', async ({ page }) => {
    // Click create button
    await page.click('button:has-text("创建"), button:has-text("新建")')

    // Fill form
    const nameInput = page.locator('input[placeholder*="名称"], input[placeholder*="name"], input[label*="名称"]')
    if (await nameInput.isVisible()) {
      await nameInput.fill(`Test KB ${Date.now()}`)
    }

    // Submit form
    const submitButton = page.locator('.el-dialog button:has-text("确定"), .el-dialog button:has-text("创建"), button[type="submit"]')
    if (await submitButton.isVisible()) {
      await submitButton.click()
    }

    // Wait for creation
    await page.waitForTimeout(1000)
  })

  test('should display knowledge base cards', async ({ page }) => {
    // If knowledge bases exist, cards should be visible
    const cards = page.locator('.knowledge-card, .el-card')
    const count = await cards.count()

    if (count > 0) {
      await expect(cards.first()).toBeVisible()
    }
  })

  test('should navigate to knowledge base detail', async ({ page }) => {
    // If there's a knowledge base card, click to view details
    const card = page.locator('.knowledge-card, .el-card').first()

    if (await card.isVisible()) {
      await card.click()

      // Should navigate to detail page
      await page.waitForTimeout(500)

      // Check URL contains knowledge ID
      expect(page.url()).toMatch(/\/knowledge\/[a-z0-9-]+/)
    }
  })
})

test.describe('Knowledge Base Detail Page', () => {
  test.skip('should display knowledge base details', async ({ page }) => {
    // This test requires an existing knowledge base
    // Navigate to detail page would require knowledge of existing KB ID
    await page.goto('/knowledge/6facc341-6281-4ecb-8a19-c8e0c9201446')

    // Check tabs
    await expect(page.locator('.el-tabs')).toBeVisible()
  })

  test.skip('should display document list', async ({ page }) => {
    await page.goto('/knowledge/6facc341-6281-4ecb-8a19-c8e0c9201446')

    // Documents tab should be visible
    const documentsTab = page.locator('.el-tabs__item:has-text("文档")')
    if (await documentsTab.isVisible()) {
      await documentsTab.click()
    }

    // Table should be visible
    await expect(page.locator('.el-table, table')).toBeVisible()
  })

  test.skip('should handle document upload', async ({ page }) => {
    await page.goto('/knowledge/6facc341-6281-4ecb-8a19-c8e0c9201446')

    // Click upload button
    const uploadButton = page.locator('button:has-text("上传"), button:has-text("Upload")')
    if (await uploadButton.isVisible()) {
      await uploadButton.click()
    }
  })
})

test.describe('Admin Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin')
  })

  test('should display admin settings', async ({ page }) => {
    // Check for configuration sections
    await expect(page.locator('.admin-container, .admin-view')).toBeVisible()
  })

  test('should display retrieval configuration', async ({ page }) => {
    // Should show vector weight and BM25 weight
    await expect(page.locator('text=/向量|Vector/i, text=/BM25/i')).toBeVisible()
  })

  test('should display system statistics', async ({ page }) => {
    // Statistics cards should be visible
    const stats = page.locator('.stat-card, .el-statistic, .stat-value')

    if (await stats.count() > 0) {
      await expect(stats.first()).toBeVisible()
    }
  })

  test('should update retrieval configuration', async ({ page }) => {
    // Find sliders or inputs for configuration
    const vectorWeight = page.locator('input[type="range"], input[type="number"]').first()

    if (await vectorWeight.isVisible()) {
      // Try to interact with the input
      await vectorWeight.fill('0.8')
    }
  })
})

test.describe('Workflow Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/workflow')
  })

  test('should display workflow diagram', async ({ page }) => {
    await expect(page.locator('.workflow-container, .workflow-view')).toBeVisible()
  })

  test('should display workflow nodes', async ({ page }) => {
    // Should have at least intent, retrieval, answer nodes
    const nodes = page.locator('.workflow-node, .node')
    const count = await nodes.count()

    expect(count).toBeGreaterThanOrEqual(3)
  })
})

test.describe('Authentication', () => {
  test('should display login page', async ({ page }) => {
    // If there's a login page, check it
    await page.goto('/login')

    // Should have login form
    await expect(page.locator('input[placeholder*="用户名"], input[placeholder*="username"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
  })

  test('should be able to login', async ({ page }) => {
    await page.goto('/login')

    const usernameInput = page.locator('input[placeholder*="用户名"], input[placeholder*="username"], input[name="username"]')
    const passwordInput = page.locator('input[type="password"]')

    if (await usernameInput.isVisible() && await passwordInput.isVisible()) {
      await usernameInput.fill('test_user')
      await passwordInput.fill('test123456')

      const loginButton = page.locator('button:has-text("登录"), button:has-text("Login"), button[type="submit"]')
      await loginButton.click()

      // Should redirect or show success
      await page.waitForTimeout(2000)
    }
  })
})

test.describe('Accessibility', () => {
  test('should have proper headings', async ({ page }) => {
    await page.goto('/')

    // Should have an h1
    await expect(page.locator('h1')).toBeVisible()
  })

  test('should have proper form labels', async ({ page }) => {
    await page.goto('/login')

    // Inputs should have accessible labels
    const inputs = page.locator('input')
    const count = await inputs.count()

    for (let i = 0; i < count; i++) {
      const input = inputs.nth(i)
      const hasLabel = await input.getAttribute('aria-label') ||
                       await input.getAttribute('placeholder') ||
                       await input.locator('xpath=ancestor::*[contains(@class, "el-form-item")]//label').count() > 0

      expect(hasLabel).toBeTruthy()
    }
  })
})