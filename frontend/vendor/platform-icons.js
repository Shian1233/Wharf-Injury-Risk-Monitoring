import { h } from 'vue'

// 用 innerHTML 承载图形，省掉为每个图标写一遍 svg 外壳。
// 内容全是本地常量，不接受外部输入
const line = (inner, opts = {}) => ({
  render: () => h('svg', {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': opts.width || 1.7,
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    innerHTML: inner
  })
})

export const IconChat = line('<path d="M20 15.5a2.5 2.5 0 0 1-2.5 2.5H8.6L4 21.2V6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v9Z"/>')

export const IconAgent = line(`
  <rect x="4" y="7.5" width="16" height="12" rx="3.5"/>
  <path d="M12 3.2v4.3M2.6 12.5v3M21.4 12.5v3"/>
  <circle cx="9.2" cy="13.2" r="1.15" fill="currentColor" stroke="none"/>
  <circle cx="14.8" cy="13.2" r="1.15" fill="currentColor" stroke="none"/>`)

export const IconBook = line(`
  <path d="M12 6.6c-1.7-1.4-4-2-6.6-2-.8 0-1.4.6-1.4 1.4v11c0 .8.6 1.4 1.4 1.4 2.6 0 4.9.6 6.6 2 1.7-1.4 4-2 6.6-2 .8 0 1.4-.6 1.4-1.4V6c0-.8-.6-1.4-1.4-1.4-2.6 0-4.9.6-6.6 2Z"/>
  <path d="M12 6.6v13.8"/>`)

export const IconChip = line(`
  <rect x="5.4" y="5.4" width="13.2" height="13.2" rx="2.6"/>
  <rect x="9.4" y="9.4" width="5.2" height="5.2" rx="1.2"/>
  <path d="M9.2 2.6v2.8M14.8 2.6v2.8M9.2 18.6v2.8M14.8 18.6v2.8M2.6 9.2h2.8M2.6 14.8h2.8M18.6 9.2h2.8M18.6 14.8h2.8"/>`)

export const IconEco = line(`
  <rect x="3.6" y="3.6" width="7" height="7" rx="1.6"/>
  <rect x="13.4" y="3.6" width="7" height="7" rx="3.5"/>
  <rect x="3.6" y="13.4" width="7" height="7" rx="1.6"/>
  <path d="M13.4 16.9h7M16.9 13.4v7"/>`)

export const IconGrid = line(`
  <rect x="3.6" y="3.6" width="7" height="7" rx="1.6"/>
  <rect x="13.4" y="3.6" width="7" height="7" rx="1.6"/>
  <rect x="3.6" y="13.4" width="7" height="7" rx="1.6"/>
  <rect x="13.4" y="13.4" width="7" height="7" rx="1.6"/>`)

export const IconBell = line(`
  <path d="M18 16.2V11a6 6 0 1 0-12 0v5.2l-1.4 2.1h14.8L18 16.2Z"/>
  <path d="M10 21.1a2.3 2.3 0 0 0 4 0"/>`)

export const IconChevronDown = line('<path d="m6.5 9.5 5.5 5.5 5.5-5.5"/>', { width: 1.8 })

export const IconChevronLeft = line('<path d="m14.5 6.5-5 5.5 5 5.5"/>', { width: 2 })

export const IconPerson = line(`
  <circle cx="12" cy="8.4" r="3.9"/>
  <path d="M4.8 20c.5-3.6 3.6-5.6 7.2-5.6s6.7 2 7.2 5.6"/>`)

export const IconHelp = line(`
  <circle cx="12" cy="12" r="8.6"/>
  <path d="M9.7 9.6a2.35 2.35 0 0 1 4.55.8c0 1.6-2.25 2-2.25 3.3"/>
  <circle cx="12" cy="16.6" r=".95" fill="currentColor" stroke="none"/>`)

export const IconLogout = line(`
  <path d="M9.5 4.5H5.4A1.4 1.4 0 0 0 4 5.9v12.2a1.4 1.4 0 0 0 1.4 1.4h4.1"/>
  <path d="m15.4 8.6 3.4 3.4-3.4 3.4"/>
  <path d="M18.8 12H9.5"/>`)

export const IconMenu = line('<path d="M4 7h16M4 12h16M4 17h16"/>')

export const IconSun = line(`
  <circle cx="12" cy="12" r="4.2"/>
  <path d="M12 2.8v2.4M12 18.8v2.4M4.7 4.7l1.7 1.7M17.6 17.6l1.7 1.7M2.8 12h2.4M18.8 12h2.4M4.7 19.3l1.7-1.7M17.6 6.4l1.7-1.7"/>`)
