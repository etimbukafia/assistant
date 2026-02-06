// =====================================================
// GOOGLE APPS SCRIPT - Paste this into your Google Sheet
// =====================================================
// 
// SETUP INSTRUCTIONS:
// 1. Open your Google Sheet
// 2. Go to Extensions → Apps Script
// 3. Delete any existing code and paste this entire file
// 4. Click Deploy → New deployment
// 5. Select "Web app" as the type
// 6. Set "Who has access" to "Anyone"
// 7. Click Deploy and copy the URL
// 8. Add that URL to your .env as GOOGLE_SCRIPT_URL
//
// =====================================================

function doPost(e) {
    try {
        const data = JSON.parse(e.postData.contents);
        const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

        // Add header row if sheet is empty
        if (sheet.getLastRow() === 0) {
            sheet.appendRow(['Timestamp', 'Name', 'Email', 'LinkedIn']);
        }

        // Append the new signup
        sheet.appendRow([
            new Date().toISOString(),
            data.name || '',
            data.email || '',
            data.linkedin || ''
        ]);

        return ContentService
            .createTextOutput(JSON.stringify({ success: true }))
            .setMimeType(ContentService.MimeType.JSON);

    } catch (error) {
        return ContentService
            .createTextOutput(JSON.stringify({ error: error.message }))
            .setMimeType(ContentService.MimeType.JSON);
    }
}

// Required for CORS preflight
function doGet(e) {
    return ContentService
        .createTextOutput(JSON.stringify({ status: 'ok' }))
        .setMimeType(ContentService.MimeType.JSON);
}
