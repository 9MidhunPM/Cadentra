export const paymentMethods = [
  { code: 'MANUAL', label: 'Manual' },
  { code: 'BANK_TRANSFER', label: 'Bank transfer' },
  { code: 'UPI', label: 'UPI' },
  { code: 'CASH', label: 'Cash' },
  { code: 'CARD_EXTERNAL', label: 'External card' },
  { code: 'OTHER', label: 'Other' },
] as const;

export function paymentMethodLabel(method: string): string {
  return paymentMethods.find(option => option.code === method)?.label ?? method;
}
