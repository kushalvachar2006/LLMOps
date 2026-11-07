import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { ThemeProvider } from '../context/providers'
import Landing from './Landing'

const setup = () => render(<ThemeProvider><MemoryRouter><Landing /></MemoryRouter></ThemeProvider>)

describe('landing page', () => {
  it('states the purpose of the project clearly', () => {
    setup()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Ship LLM features you can prove works/i)
    expect(screen.getByText(/write prompts, test them against your own data/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /LLM apps fail quietly/i })).toBeInTheDocument()
    expect(screen.getByText(/regressions from their users/i)).toBeInTheDocument()
  })

  it('links the main calls to action to the workspace', () => {
    setup()
    const open = screen.getAllByRole('link', { name: /open (the )?workspace/i })
    expect(open.length).toBeGreaterThanOrEqual(2)
    open.forEach((a) => expect(a).toHaveAttribute('href', '/app'))
    expect(screen.getByRole('link', { name: /try the playground/i })).toHaveAttribute('href', '/app/playground')
  })

  it('has navigation anchors that point at real sections', () => {
    setup()
    for (const id of ['why', 'lifecycle', 'features', 'developers', 'principles', 'faq']) {
      expect(document.getElementById(id), id).not.toBeNull()
      expect(screen.getAllByRole('link').some((a) => a.getAttribute('href') === `#${id}`), id).toBe(true)
    }
  })

  it('lets visitors explore the lifecycle interactively', async () => {
    setup()
    const tabs = within(screen.getByRole('tablist', { name: /product lifecycle/i })).getAllByRole('tab')
    expect(tabs).toHaveLength(6)
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    await userEvent.click(tabs[3])
    expect(tabs[3]).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText(/Model-judge scores are kept separate/i)).toBeInTheDocument()
    expect(await screen.findByText(/A judge score is an opinion/i)).toBeInTheDocument()
    await userEvent.click(tabs[4])
    expect(await screen.findByText(/POST \/v1\/deployments/)).toBeInTheDocument()
  })

  it('shows developer code in three languages', async () => {
    setup()
    const tablist = screen.getAllByRole('tablist').find((t) => within(t).queryByRole('tab', { name: 'Python' }))
    expect(within(tablist).getAllByRole('tab').map((t) => t.textContent)).toEqual(['curl', 'JavaScript', 'Python'])
    await userEvent.click(within(tablist).getByRole('tab', { name: 'Python' }))
    expect(within(tablist).getByRole('tab', { name: 'Python' })).toHaveAttribute('aria-selected', 'true')
  })

  it('answers common questions in an accordion', async () => {
    setup()
    const q = screen.getByRole('button', { name: /Is my prompt text stored/i })
    expect(q).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(q)
    expect(q).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByText(/Only metadata is stored|only metadata is stored/i)).toBeInTheDocument()
  })

  it('does not overclaim: illustrations are labelled and there are no customer or benchmark claims', () => {
    setup()
    expect(screen.getAllByText(/Illustration with sample values|Illustrative preview/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Illustrations on this page use sample data/i)).toBeInTheDocument()
    const text = document.body.textContent
    expect(text).not.toMatch(/trusted by|customers|% faster|10x|guarantee/i)
  })

  it('switches between dark and light themes', async () => {
    setup()
    const btn = screen.getAllByRole('button', { name: /switch to light theme/i })[0]
    await userEvent.click(btn)
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('llmops.theme')).toBe('light')
    await userEvent.click(screen.getAllByRole('button', { name: /switch to dark theme/i })[0])
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('opens and closes the mobile menu', async () => {
    setup()
    const burger = screen.getByRole('button', { name: /toggle menu/i })
    expect(burger).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(burger)
    expect(burger).toHaveAttribute('aria-expanded', 'true')
  })
})
