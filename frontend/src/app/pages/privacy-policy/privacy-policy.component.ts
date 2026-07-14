import { Component } from '@angular/core'
import { CommonModule } from '@angular/common'
import { RouterLink } from '@angular/router'

@Component({
  selector: 'app-privacy-policy',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="privacy-container">
      <div class="privacy-content">
        <div class="privacy-header">
          <a routerLink="/knowledge" class="back-link">← Back</a>
          <h1>Data Privacy & What Leaves Your Device</h1>
        </div>

        <section class="privacy-section">
          <h2>Local-First Architecture</h2>
          <p>
            Knowledge Hubs is designed with <strong>privacy as the default</strong>. All processing happens on your machine by default — nothing leaves your device unless you explicitly enable cloud providers.
          </p>
        </section>

        <section class="privacy-section">
          <h2>Local Mode (Default)</h2>
          <p>When using local models:</p>
          <ul>
            <li>Text you ingest never leaves your machine</li>
            <li>AI processing (extraction, linking, embedding) runs locally</li>
            <li>The knowledge graph is stored locally</li>
            <li>Search and context retrieval are entirely local</li>
          </ul>
          <p class="highlight">✓ <strong>Nothing leaves your device.</strong></p>
        </section>

        <section class="privacy-section">
          <h2>Cloud Mode (Optional)</h2>
          <p>If you enable cloud providers:</p>
          <ul>
            <li>You explicitly configure which cloud services to use (e.g., OpenAI)</li>
            <li>Cloud processing is opt-in per workspace, not automatic</li>
            <li>Only the data you explicitly send to cloud APIs leaves your device</li>
            <li>Text, code, and sensitive information should be carefully reviewed before sending to cloud</li>
          </ul>
          <p class="warning">⚠ <strong>Your cloud provider's terms of service apply.</strong> Review their privacy policies.</p>
        </section>

        <section class="privacy-section">
          <h2>Data Storage</h2>
          <ul>
            <li><strong>Authentication token:</strong> Stored in browser localStorage for session management</li>
            <li><strong>Workspace settings:</strong> Stored on the server (encrypted in transit)</li>
            <li><strong>Knowledge graph & embeddings:</strong> Stored locally on your machine</li>
            <li><strong>Ingested content:</strong> Never sent to external services unless cloud mode is enabled</li>
          </ul>
        </section>

        <section class="privacy-section">
          <h2>Model Downloads</h2>
          <p>
            When you download local models (e.g., Llama 3.1):
          </p>
          <ul>
            <li>Models are fetched from Ollama or similar registries</li>
            <li>No user data is sent during model download — only the model binary itself</li>
            <li>Downloaded models are stored on your machine</li>
          </ul>
        </section>

        <section class="privacy-section">
          <h2>Browser Data</h2>
          <p>
            This web application stores in your browser:
          </p>
          <ul>
            <li>Authentication token (localStorage)</li>
            <li>Workspace ID (localStorage)</li>
            <li>UI preferences (localStorage)</li>
          </ul>
          <p>No third-party tracking or analytics are enabled by default.</p>
        </section>

        <section class="privacy-section">
          <h2>Transparency Promise</h2>
          <div class="promise-box">
            <p>
              <strong>Every AI-touched surface in the UI shows which provider is in use.</strong>
            </p>
            <p>
              Look for the badge at the top of your screen:
            </p>
            <ul>
              <li>🟢 <strong>Green "Local"</strong> — processing is happening on your machine</li>
              <li>🔵 <strong>Blue "Cloud"</strong> — data is being sent to a cloud service</li>
            </ul>
            <p>
              This makes it impossible to accidentally use cloud AI without realizing it.
            </p>
          </div>
        </section>

        <section class="privacy-section">
          <h2>GDPR & Data Rights</h2>
          <p>
            Since all user data is stored on your device by default:
          </p>
          <ul>
            <li>You have full control and ownership of your data</li>
            <li>You can delete all data by removing the application</li>
            <li>No tracking or profiling happens on local data</li>
            <li>Cloud providers (if used) are subject to their own privacy policies</li>
          </ul>
        </section>

        <section class="privacy-section last-section">
          <h2>Questions?</h2>
          <p>
            If you have questions about how your data is handled, please refer to the documentation or contact support.
          </p>
        </section>
      </div>
    </div>
  `,
  styles: [`
    .privacy-container {
      max-width: 800px;
      margin: 0 auto;
      padding: 2rem;
    }

    .privacy-header {
      margin-bottom: 3rem;
    }

    .back-link {
      display: inline-block;
      color: #0066cc;
      text-decoration: none;
      margin-bottom: 1rem;
      font-weight: 500;
    }

    .back-link:hover {
      text-decoration: underline;
    }

    h1 {
      font-size: 2rem;
      margin: 0;
      color: #333;
    }

    .privacy-section {
      margin-bottom: 2rem;
      padding-bottom: 2rem;
      border-bottom: 1px solid #e0e0e0;
    }

    .privacy-section.last-section {
      border-bottom: none;
    }

    h2 {
      font-size: 1.25rem;
      color: #333;
      margin: 0 0 1rem;
    }

    p {
      line-height: 1.6;
      color: #555;
      margin: 0.75rem 0;
    }

    ul {
      margin: 1rem 0;
      padding-left: 2rem;
    }

    li {
      margin: 0.5rem 0;
      line-height: 1.6;
      color: #555;
    }

    .highlight {
      background: #e6f7e6;
      padding: 1rem;
      border-radius: 4px;
      border-left: 4px solid #16a34a;
      margin: 1rem 0;
    }

    .warning {
      background: #fff3e0;
      padding: 1rem;
      border-radius: 4px;
      border-left: 4px solid #ff9800;
      margin: 1rem 0;
    }

    .promise-box {
      background: #f0f8ff;
      padding: 1.5rem;
      border-radius: 8px;
      border-left: 4px solid #0066cc;
    }

    strong {
      color: #333;
    }
  `],
})
export class PrivacyPolicyComponent {}
