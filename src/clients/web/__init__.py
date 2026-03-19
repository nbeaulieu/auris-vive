"""
src.clients.web — JavaScript SDK stub

The web client is a JS/TS package, not Python.  This package exists in the
monorepo as a placeholder so the directory structure reflects the architecture.

Planned surface (JS SDK):

    import { AurisViveClient } from '@auris-vive/web-sdk';

    const client = new AurisViveClient({ baseUrl: 'https://api.aurisvive.com' });
    const job    = await client.submitFile(file);          // File | Blob
    const result = await job.wait();                       // polls GET /jobs/{id}
    job.onProgress(({ stage, pct }) => { ... });           // WS stream

The actual JS/TS source will live in src/clients/web/ as a separate npm
package when that work begins.
"""
