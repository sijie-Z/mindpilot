/**
 * useConfirm composable for MindPilot.
 * Provides ElMessageBox-based confirmation dialogs replacing native confirm/prompt.
 */
import { ElMessageBox, ElMessage } from 'element-plus'

export interface ConfirmOptions {
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  type?: 'success' | 'warning' | 'info' | 'error'
  dangerouslyUseHTMLString?: boolean
}

export interface PromptOptions {
  title?: string
  message?: string
  placeholder?: string
  defaultValue?: string
  inputPattern?: RegExp
  inputErrorMessage?: string
  confirmText?: string
  cancelText?: string
}

/**
 * Confirmation dialog composable.
 * Replaces native window.confirm with Element Plus MessageBox.
 */
export function useConfirm() {
  /**
   * Show a confirmation dialog.
   * @returns Promise that resolves to true if confirmed, false if cancelled
   */
  async function confirm(options: ConfirmOptions = {}): Promise<boolean> {
    try {
      await ElMessageBox.confirm(
        options.message || '确定执行此操作吗？',
        options.title || '确认',
        {
          confirmButtonText: options.confirmText || '确定',
          cancelButtonText: options.cancelText || '取消',
          type: options.type || 'warning',
          dangerouslyUseHTMLString: options.dangerouslyUseHTMLString || false,
          closeOnClickModal: false,
          closeOnPressEscape: true,
        }
      )
      return true
    } catch {
      return false
    }
  }

  /**
   * Show a delete confirmation dialog with warning styling.
   * @param itemName Name of the item to delete
   * @returns Promise that resolves to true if confirmed
   */
  async function confirmDelete(itemName: string = '此项目'): Promise<boolean> {
    return confirm({
      title: '删除确认',
      message: `确定要删除 ${itemName} 吗？此操作不可撤销。`,
      confirmText: '删除',
      cancelText: '取消',
      type: 'error',
    })
  }

  /**
   * Show an alert dialog (only OK button).
   * @param options Dialog options
   */
  async function alert(options: ConfirmOptions = {}): Promise<void> {
    await ElMessageBox.alert(
      options.message || '',
      options.title || '提示',
      {
        confirmButtonText: options.confirmText || '确定',
        type: options.type || 'info',
        dangerouslyUseHTMLString: options.dangerouslyUseHTMLString || false,
      }
    )
  }

  /**
   * Show a prompt dialog for user input.
   * @param options Prompt options
   * @returns Promise that resolves to the input value, or null if cancelled
   */
  async function prompt(options: PromptOptions = {}): Promise<string | null> {
    try {
      const { value } = await ElMessageBox.prompt(
        options.message || '请输入',
        options.title || '输入',
        {
          confirmButtonText: options.confirmText || '确定',
          cancelButtonText: options.cancelText || '取消',
          inputPlaceholder: options.placeholder || '',
          inputValue: options.defaultValue || '',
          inputPattern: options.inputPattern,
          inputErrorMessage: options.inputErrorMessage || '输入格式不正确',
          closeOnClickModal: false,
        }
      )
      return value
    } catch {
      return null
    }
  }

  /**
   * Show a prompt for creating a new item with name.
   * @param defaultName Default name value
   * @returns Promise that resolves to the name, or null if cancelled
   */
  async function promptName(defaultName: string = ''): Promise<string | null> {
    const name = await prompt({
      title: '创建',
      message: '请输入名称',
      placeholder: '输入名称...',
      defaultValue: defaultName,
      inputPattern: /^.{1,50}$/,
      inputErrorMessage: '名称长度应在1-50个字符之间',
    })
    return name
  }

  /**
   * Show a success message toast.
   * @param message Message to display
   */
  function success(message: string): void {
    ElMessage.success(message)
  }

  /**
   * Show an error message toast.
   * @param message Message to display
   */
  function error(message: string): void {
    ElMessage.error(message)
  }

  /**
   * Show a warning message toast.
   * @param message Message to display
   */
  function warning(message: string): void {
    ElMessage.warning(message)
  }

  /**
   * Show an info message toast.
   * @param message Message to display
   */
  function info(message: string): void {
    ElMessage.info(message)
  }

  return {
    confirm,
    confirmDelete,
    alert,
    prompt,
    promptName,
    success,
    error,
    warning,
    info,
  }
}

export default useConfirm