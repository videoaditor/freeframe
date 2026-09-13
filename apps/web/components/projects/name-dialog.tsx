'use client'

import * as React from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface NameDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  placeholder?: string
  defaultValue?: string
  submitLabel?: string
  /** A SECOND field, when the thing being named needs more than a name.
   *
   *  Aditor files each hand-in as a folder, and the Trello card link has to arrive with it: it is
   *  what tells the review which brand's rules to use, which script to check and who cut it. An
   *  instance that requires it and gives nobody a box to type it in has simply stopped people
   *  creating folders, so the box and the requirement ship together.
   *
   *  Absent by default, which is every other caller of this dialog. */
  extraField?: { label: string; placeholder?: string; required?: boolean }
  onSubmit: (name: string, extra?: string) => void
}

export function NameDialog({
  open,
  onOpenChange,
  title,
  description,
  placeholder = 'Enter name...',
  defaultValue = '',
  submitLabel = 'Create',
  extraField,
  onSubmit,
}: NameDialogProps) {
  const [value, setValue] = React.useState(defaultValue)
  const [extra, setExtra] = React.useState('')
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (open) {
      setValue(defaultValue)
      setExtra('')
    }
  }, [open, defaultValue])

  const extraMissing = !!extraField?.required && !extra.trim()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || extraMissing) return
    onSubmit(trimmed, extraField ? extra.trim() : undefined)
    onOpenChange(false)
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-bg-secondary p-5 shadow-xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95"
          onOpenAutoFocus={(e) => {
            e.preventDefault()
            inputRef.current?.focus()
            inputRef.current?.select()
          }}
        >
          <Dialog.Close className="absolute right-3 top-3 text-text-tertiary hover:text-text-primary transition-colors">
            <X className="h-4 w-4" />
          </Dialog.Close>

          <Dialog.Title className="text-sm font-semibold text-text-primary">
            {title}
          </Dialog.Title>
          {description && (
            <Dialog.Description className="mt-1 text-xs text-text-tertiary">
              {description}
            </Dialog.Description>
          )}

          <form onSubmit={handleSubmit} className="mt-3 space-y-3">
            <Input
              ref={inputRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={placeholder}
              autoComplete="off"
            />
            {extraField && (
              <div className="space-y-1">
                <label className="text-xs text-text-tertiary" htmlFor="name-dialog-extra">
                  {extraField.label}
                </label>
                <Input
                  id="name-dialog-extra"
                  value={extra}
                  onChange={(e) => setExtra(e.target.value)}
                  placeholder={extraField.placeholder}
                  autoComplete="off"
                />
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={!value.trim() || extraMissing}>
                {submitLabel}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
