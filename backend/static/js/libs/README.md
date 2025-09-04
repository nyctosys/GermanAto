# Local JavaScript Libraries

This directory contains locally hosted JavaScript libraries that were previously loaded from CDNs.

## Libraries Included

### 1. html2canvas.min.js

- **Version**: 1.4.1
- **Original CDN**: https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js
- **Usage**: Used in invoice-template.html for converting HTML to canvas for PDF generation

### 2. jspdf.umd.min.js

- **Version**: 2.5.1
- **Original CDN**: https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js
- **Usage**: Used in invoice-template.html for PDF generation

### 3. chart.js

- **Original CDN**: https://cdn.jsdelivr.net/npm/chart.js
- **Usage**: Used in reports.html for creating charts and graphs

### 4. xlsx.full.min.js

- **Version**: 0.18.5
- **Original CDN**: https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js
- **Usage**: Used in low-stock-print.html for Excel file operations

## Benefits of Local Hosting

1. **Offline Functionality**: The application can work without internet connectivity
2. **Performance**: Faster loading times as libraries are served from the same server
3. **Reliability**: No dependency on external CDN availability
4. **Security**: Reduced risk from compromised CDNs
5. **Version Control**: Guaranteed library versions that won't change unexpectedly

## Maintenance

To update these libraries:

1. Download the new version from the original CDN
2. Replace the corresponding file in this directory
3. Test the application to ensure compatibility
4. Update this README with the new version information
