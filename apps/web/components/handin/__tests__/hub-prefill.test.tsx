import { beforeEach, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import HandinPage from "@/app/(dashboard)/handin/page";
import { lookUpCard } from "@/lib/handin";
const { startUpload, uploadFiles } = vi.hoisted(() => ({ startUpload: vi.fn(), uploadFiles: [] }));
vi.mock("swr", () => ({ default: () => ({ data: [] }) }));
vi.mock("@/lib/handin", async (original) => ({
  ...await original<typeof import("@/lib/handin")>(),
  isHandinConfigured: () => true,
  lookUpCard: vi.fn(),
}));
vi.mock("@/stores/upload-store", () => ({ useUploadStore: (select: (s: unknown) => unknown) => select({ startUpload, files: uploadFiles }) }));
vi.mock("@/stores/auth-store", () => ({ useAuthStore: (select: (s: unknown) => unknown) => select({ user: null, isSuperAdmin: false }) }));
vi.mock("@/components/upload/upload-zone", () => ({ UploadZone: () => <div>File picker</div> }));
beforeEach(() => { vi.clearAllMocks(); window.history.replaceState({}, "", "/handin?card=" + encodeURIComponent("https://trello.com/c/VUFKsrxi/a-title")); });
it("prefills and resolves the Hub card while leaving upload to the editor", async () => {
  vi.mocked(lookUpCard).mockResolvedValue({ name: "Nackenkissen", brand: "Liebscher & Bracht" });
  render(<HandinPage />);
  expect(screen.getByLabelText(/trello card/i)).toHaveValue("https://trello.com/c/VUFKsrxi");
  expect(await screen.findByTestId("card-confirmation")).toHaveTextContent("Nackenkissen");
  expect(lookUpCard).toHaveBeenCalledWith("https://trello.com/c/VUFKsrxi");
  expect(startUpload).not.toHaveBeenCalled();
});
it("ignores an old lookup when the editor changes the prefilled card", async () => {
  let resolve!: (card: { name: string }) => void;
  vi.mocked(lookUpCard).mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  render(<HandinPage />);
  await waitFor(() => expect(lookUpCard).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText(/trello card/i), { target: { value: "https://trello.com/c/12345678" } });
  await act(async () => resolve({ name: "Old card" }));
  expect(screen.queryByText("Old card")).toBeNull();
  expect(screen.getByLabelText(/trello card/i)).toHaveValue("https://trello.com/c/12345678");
});
it("does not look up an untrusted prefill", () => {
  window.history.replaceState({}, "", "/handin?card=https://trello.com.evil.test/c/VUFKsrxi");
  render(<HandinPage />);
  expect(screen.getByLabelText(/trello card/i)).toHaveValue("");
  expect(lookUpCard).not.toHaveBeenCalled();
});

it("resolves a pasted replacement after a Hub prefill", async () => {
  vi.mocked(lookUpCard).mockResolvedValueOnce({ name: "Original card" }).mockResolvedValueOnce({ name: "Replacement card" });
  render(<HandinPage />);
  await screen.findByText("Original card");
  fireEvent.paste(screen.getByLabelText(/trello card/i), { clipboardData: { getData: () => "https://trello.com/c/12345678" } });
  expect(await screen.findByText("Replacement card")).toBeVisible();
  expect(screen.getByLabelText(/trello card/i)).toHaveValue("https://trello.com/c/12345678");
});
