export function getPaymentStatusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

export function formatCryptoAmount(amount: number, currency: string): string {
  const decimals = currency === "USDT" ? 2 : 8;
  return `${amount.toFixed(decimals)} ${currency}`;
}

export function formatFiatAmount(amount: number): string {
  return `$${amount.toFixed(2)} USD`;
}

export function getPaymentProgressMessage(
  status: string,
  confirmations: number,
  requiredConfirmations: number,
): string {
  if (status === "PAID") {
    return "Payment confirmed. Your upgrade is active.";
  }
  if (status === "CONFIRMING") {
    return `Confirming on-chain (${confirmations}/${requiredConfirmations})…`;
  }
  if (status === "AWAITING_PAYMENT") {
    return "Waiting for payment to the invoice address.";
  }
  if (status === "EXPIRED") {
    return "This invoice has expired. Create a new invoice to continue.";
  }
  if (status === "UNDERPAID") {
    return "Payment received but amount was insufficient.";
  }
  return getPaymentStatusLabel(status);
}

export function buildQrCodeUrl(paymentUri: string | null | undefined): string | null {
  if (!paymentUri) {
    return null;
  }
  return `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(paymentUri)}`;
}
