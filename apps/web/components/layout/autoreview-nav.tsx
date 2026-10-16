'use client'

import * as React from 'react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import useSWR from 'swr'
import { Loader2, ScanEye } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/shared/toast'

interface AutoreviewBrand {
  slug: string
  name: string
}

/** Sidebar entry to the user's AutoReview brand page (Brand Loop B3). The link carries a 60 s
 * token, so it is minted on click, never rendered ahead. Hidden without a linked brand. */
export function AutoreviewNav({ collapsed }: { collapsed: boolean }) {
  const { data } = useSWR<{ brands: AutoreviewBrand[] }>('/autoreview/brands', () =>
    api.get<{ brands: AutoreviewBrand[] }>('/autoreview/brands'),
  )
  const [pending, setPending] = React.useState(false)
  const toast = useToast()
  const brands = data?.brands ?? []
  if (brands.length === 0) return null

  const open = async (slug: string) => {
    if (pending) return
    setPending(true)
    try {
      const { url } = await api.get<{ url: string }>(`/autoreview/link?brand=${encodeURIComponent(slug)}`)
      window.location.assign(url)
    } catch {
      setPending(false)
      toast.error("Couldn't open AutoReview. Try again.")
    }
  }

  const Icon = pending ? Loader2 : ScanEye
  const row = (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button
      type="button"
      aria-label="AutoReview"
      aria-busy={pending || undefined}
      title={collapsed ? 'AutoReview' : undefined}
      className={cn(
        'group relative flex w-full items-center rounded-md transition-colors duration-100',
        'text-text-secondary hover:bg-bg-hover/60 hover:text-text-primary data-[state=open]:bg-bg-hover data-[state=open]:text-text-primary',
        collapsed ? 'justify-center h-11 w-11 mx-auto' : 'gap-3 px-3 h-11',
      )}
      {...props}
    >
      <Icon className={cn('h-[18px] w-[18px] shrink-0', pending && 'animate-spin')} strokeWidth={1.5} />
      {!collapsed && <span className="text-[13px]">AutoReview</span>}
    </button>
  )

  if (brands.length === 1) return row({ onClick: () => open(brands[0].slug) })

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>{row({})}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side="right"
          align="start"
          sideOffset={8}
          className="z-50 min-w-[180px] rounded-lg border border-border bg-bg-elevated p-1 shadow-xl animate-slide-up"
        >
          {brands.map((brand) => (
            <DropdownMenu.Item
              key={brand.slug}
              onSelect={() => open(brand.slug)}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-2 text-[13px] text-text-secondary hover:bg-bg-hover hover:text-text-primary focus:outline-none data-[highlighted]:bg-bg-hover data-[highlighted]:text-text-primary"
            >
              {brand.name}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
