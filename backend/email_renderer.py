"""Render polished, email-client-friendly HTML from plain-text copy."""

from html import escape


def render_html_email(body: str, company_name: str = "AI Solutions",
                      recipient_name: str = "") -> str:
    paragraphs = [part.strip() for part in body.split("\n\n") if part.strip()]
    safe_paragraphs = "\n".join(
        f'<p style="margin:0 0 18px;color:#263246;font-size:15px;line-height:1.7">'
        f'{escape(paragraph).replace(chr(10), "<br>")}</p>'
        for paragraph in paragraphs
    )
    preheader = escape(f"A personal note for {recipient_name}" if recipient_name else "A personal note")
    brand = escape(company_name or "AI Solutions")
    return f'''<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
  <body style="margin:0;background:#f2f5f9;font-family:Arial,Helvetica,sans-serif">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0">{preheader}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f2f5f9;padding:32px 12px">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#fff;border:1px solid #e5eaf1;border-radius:14px;overflow:hidden">
          <tr><td style="height:5px;background:#635bff;font-size:0;line-height:0">&nbsp;</td></tr>
          <tr><td style="padding:28px 36px 8px">
            <div style="color:#635bff;font-size:12px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase">{brand}</div>
          </td></tr>
          <tr><td style="padding:18px 36px 24px">{safe_paragraphs}</td></tr>
          <tr><td style="padding:0 36px"><div style="height:1px;background:#e9edf3"></div></td></tr>
          <tr><td style="padding:18px 36px 26px;color:#7b8798;font-size:12px;line-height:1.6">
            A personal message from {brand}.<br>
            If this isn’t relevant, no reply is needed.
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>'''
