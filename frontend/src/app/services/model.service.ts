import { Injectable, signal, computed } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { firstValueFrom } from 'rxjs'
import { AuthService, API_BASE } from './auth.service'

export interface LocalModel {
  id: string
  name: string
  size: string
  ramRequired: string
  provider: 'ollama' | 'local'
  installed: boolean
  downloading?: boolean
  progress?: number
}

export interface EmbeddingModel {
  id: string
  name: string
  provider: 'local' | 'openai'
}

export interface ModelStatus {
  llm: {
    provider: 'local' | 'cloud'
    model?: string
    installed?: boolean
  }
  embedding: {
    provider: 'local' | 'openai'
    model?: string
    installed?: boolean
  }
  cloudEnabled?: boolean
}

export interface SystemInfo {
  ramGb: number
  recommendedTier: string
}

@Injectable({ providedIn: 'root' })
export class ModelService {
  private _modelStatus = signal<ModelStatus | null>(null)
  private _localModels = signal<LocalModel[]>([])
  private _systemInfo = signal<SystemInfo | null>(null)
  private _cloudEnabled = signal<boolean>(false)

  readonly modelStatus = this._modelStatus.asReadonly()
  readonly localModels = this._localModels.asReadonly()
  readonly systemInfo = this._systemInfo.asReadonly()
  readonly cloudEnabled = this._cloudEnabled.asReadonly()

  readonly currentLlmProvider = computed(() => {
    const status = this._modelStatus()
    if (!status) return 'not-configured'
    return status.llm.provider === 'local' ? 'local' : 'cloud'
  })

  readonly currentLlmModel = computed(() => {
    const status = this._modelStatus()
    return status?.llm.model || 'Not configured'
  })

  readonly statusBadgeColor = computed(() => {
    const provider = this.currentLlmProvider()
    if (provider === 'local') return 'green'
    if (provider === 'cloud') return 'blue'
    return 'red'
  })

  readonly statusBadgeText = computed(() => {
    const provider = this.currentLlmProvider()
    const model = this.currentLlmModel()
    if (provider === 'local') return `🟢 Local · ${model}`
    if (provider === 'cloud') return `🔵 Cloud · ${model}`
    return '🔴 Not configured'
  })

  constructor(private http: HttpClient, private auth: AuthService) {
    this.loadModelStatus()
    this.loadSystemInfo()
  }

  async loadModelStatus(): Promise<void> {
    try {
      const status = await firstValueFrom(
        this.http.get<ModelStatus>(`${API_BASE}/models/status`, { headers: this.auth.authHeaders() })
      )
      this._modelStatus.set(status)
      this._cloudEnabled.set(!!status.cloudEnabled)
    } catch (error) {
      console.error('Failed to load model status:', error)
    }
  }

  async loadSystemInfo(): Promise<void> {
    try {
      const info = await firstValueFrom(
        this.http.get<SystemInfo>(`${API_BASE}/models/system-info`, { headers: this.auth.authHeaders() })
      )
      this._systemInfo.set(info)
    } catch (error) {
      console.error('Failed to load system info:', error)
    }
  }

  async loadLocalModels(): Promise<void> {
    try {
      const models = await firstValueFrom(
        this.http.get<LocalModel[]>(`${API_BASE}/models/local`, { headers: this.auth.authHeaders() })
      )
      this._localModels.set(models)
    } catch (error) {
      console.error('Failed to load local models:', error)
    }
  }

  async installModel(modelId: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${API_BASE}/models/install`, { model_id: modelId }, { headers: this.auth.authHeaders() })
      )
      await this.loadLocalModels()
      await this.loadModelStatus()
    } catch (error) {
      console.error('Failed to install model:', error)
    }
  }

  async removeModel(modelId: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${API_BASE}/models/remove`, { model_id: modelId }, { headers: this.auth.authHeaders() })
      )
      await this.loadLocalModels()
      await this.loadModelStatus()
    } catch (error) {
      console.error('Failed to remove model:', error)
    }
  }

  async setDefaultModel(modelId: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${API_BASE}/models/set-default`, { model_id: modelId }, { headers: this.auth.authHeaders() })
      )
      await this.loadModelStatus()
    } catch (error) {
      console.error('Failed to set default model:', error)
    }
  }

  async toggleCloudProvider(enabled: boolean): Promise<void> {
    try {
      this._cloudEnabled.set(enabled)
      await firstValueFrom(
        this.http.patch(`${API_BASE}/workspace/settings`, { allow_cloud_providers: enabled }, { headers: this.auth.authHeaders() })
      )
      await this.loadModelStatus()
    } catch (error) {
      console.error('Failed to toggle cloud provider:', error)
      this._cloudEnabled.set(!enabled)
    }
  }

  /**
   * POST the real API key to the backend, which Fernet-encrypts it before
   * writing to the database. The plaintext never touches disk.
   * Returns the opaque config_id ref the caller can store client-side.
   */
  async saveApiKey(provider: string, apiKey: string): Promise<string> {
    const data: any = await firstValueFrom(
      this.http.post(
        `${API_BASE}/workspace/api-key`,
        { provider, api_key: apiKey },
        { headers: this.auth.authHeaders() }
      )
    )
    await this.loadModelStatus()
    return data.config_id as string
  }
}
