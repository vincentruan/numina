/// <reference types="vite/client" />

// qrcode — @types/qrcode is installed but tsconfig `types: ["vite/client"]`
// restricts auto-inclusion of @types/* packages. Declare the module so the
// default import resolves without adding it to the global types array.
declare module 'qrcode' {
  interface QRCodeToDataURLOptions {
    errorCorrectionLevel?: 'low' | 'medium' | 'quartile' | 'high' | 'L' | 'M' | 'Q' | 'H'
    margin?: number
    scale?: number
    width?: number
    color?: {
      dark?: string
      light?: string
    }
  }

  interface QRCodeToStringOptions extends QRCodeToDataURLOptions {
    type?: 'terminal' | 'svg' | 'utf8'
  }

  function toDataURL(text: string, options?: QRCodeToDataURLOptions): Promise<string>
  function toString(text: string, options?: QRCodeToStringOptions): Promise<string>

  const qrcode: {
    toDataURL: typeof toDataURL
    toString: typeof toString
  }
  export default qrcode
}
