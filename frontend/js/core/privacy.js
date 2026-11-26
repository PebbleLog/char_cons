/* 首次调用第三方服务前的告知与确认。确认状态保存在本地后端，不使用浏览器存储。 */

import { settingsApi } from './api.js';
import { openConfirm } from './modal.js';
import { toast } from './ui.js';

const MESSAGES = {
  generation:
    '重新生成会把当前镜头、参考镜头与修正提示词发送至你配置的图像生成服务，并把候选图发送至视觉模型进行预检。图片仅用于本次请求，不会上传至自建服务器。生成服务可能按张计费；本工具不会再次弹出费用确认。是否同意并继续？',
  analysis:
    '连接测试会向已配置的分析服务发送一条最小文本请求，用于验证鉴权与网络。不会发送本地镜头图片。是否同意并继续？',
  analysis_run:
    '开始分析会把本任务的镜头图片与角色设定发送至你配置的视觉模型，用于观察与一致性判定。图片仅用于本次分析请求，不会上传至自建服务器。是否同意并继续？',
  generation_test:
    '连接测试会向已配置的图像生成服务发起 1 次最小生成请求，可能产生图片费用；不会发送本地镜头图片。是否同意并继续？',
};

export async function ensurePrivacyAcknowledged(scope = 'generation') {
  try {
    const data = await settingsApi.get();
    if (data.privacyAcknowledged) return true;
    return await openConfirm({
      title: '第三方服务调用告知',
      message: MESSAGES[scope] || MESSAGES.generation,
      confirmText: '同意并继续',
      busyText: '记录中…',
      onConfirm: async () => {
        await settingsApi.update({ privacyAcknowledged: true });
        return true;
      },
    });
  } catch (error) {
    toast(error.message || '无法读取本地隐私设置');
    return false;
  }
}
