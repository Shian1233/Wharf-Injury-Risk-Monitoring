<template>
  <section id="page-header" class="demo-section">
    <h2 class="demo-section__title">PageHeader 页面标题栏</h2>

    <div class="demo-block control-showcase">
      <div class="control-showcase__main">
        <p class="demo-label">页面标题栏</p>
        <div class="page-header-stage">
          <PageHeader
            :title="title"
            :description="showDesc ? description : ''"
            :breadcrumb="level === 3 ? crumbs : undefined"
            :show-back="level !== 1"
            @back="noop"
          >
            <template v-if="actionType !== 'none'" #extra>
              <!-- 纯图标：.btn-icon-square + tooltip + aria-label -->
              <template v-if="actionType === 'icon'">
                <el-tooltip v-for="a in iconActions" :key="a.label" :content="a.label" placement="top">
                  <el-button class="btn-icon-square" :aria-label="a.label">
                    <template #icon><component :is="a.icon" :size="16" :stroke-width="2" /></template>
                  </el-button>
                </el-tooltip>
              </template>
              <!-- 文字 -->
              <template v-else-if="actionType === 'text'">
                <el-button>历史对话</el-button>
                <el-button>新对话</el-button>
              </template>
              <!-- 图标 + 文字 -->
              <template v-else>
                <el-button>
                  <template #icon><History :size="16" :stroke-width="2" /></template>
                  历史对话
                </el-button>
                <el-button>
                  <template #icon><Plus :size="16" :stroke-width="2" /></template>
                  新对话
                </el-button>
              </template>
            </template>
          </PageHeader>
        </div>
      </div>

      <aside class="config-card">
        <p class="config-card__title">配置项</p>
        <el-form label-width="auto">
          <el-form-item label="页面层级">
            <el-radio-group v-model="level">
              <el-radio :value="1">一级</el-radio>
              <el-radio :value="2">二级</el-radio>
              <el-radio :value="3">三级及以上</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="说明">
            <el-switch v-model="showDesc" />
          </el-form-item>
          <el-form-item label="右侧操作">
            <el-radio-group v-model="actionType">
              <el-radio value="none">无</el-radio>
              <el-radio value="icon">纯图标</el-radio>
              <el-radio value="text">文字</el-radio>
              <el-radio value="icon-text">图标+文字</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Star, BookOpen, History, Search, Plus } from 'lucide-vue-next'
import { PageHeader, type BreadcrumbItem } from '../../../../design-spec/components'

const level = ref<1 | 2 | 3>(2)
const showDesc = ref(false)
const actionType = ref<'none' | 'icon' | 'text' | 'icon-text'>('none')

const title = computed(() => (level.value === 1 ? '文献检索' : '跨模态对齐技术在自动驾驶中的应用'))
const description = '点任意一条继续该对话'

const crumbs: BreadcrumbItem[] = [
  { label: '中药复方配伍智能体' },
  { label: '药物-靶点预测' },
  { label: '我的' },
]

const iconActions = [
  { label: '论文收藏', icon: Star },
  { label: '综述列表', icon: BookOpen },
  { label: '检索历史', icon: History },
  { label: '检索', icon: Search },
]

const noop = () => {}
</script>

<style scoped>
.demo-section .demo-block {
  margin-bottom: 0;
  padding: var(--iflyv-spacing-6);
  background: var(--iflyv-bg-card);
  border-radius: var(--iflyv-radius-lg);
}

/* 承载区：模拟页面顶部，圆角裁切让页头下边线可见（纯本页排版） */
.page-header-stage {
  overflow: hidden;
  border: 1px solid var(--iflyv-border-subtle);
  border-radius: var(--iflyv-radius-md);
  background: var(--iflyv-bg-page-white);
  padding-bottom: var(--iflyv-spacing-10);
}

.control-showcase {
  display: flex;
  align-items: flex-start;
  gap: calc(var(--iflyv-spacing-8) + var(--iflyv-spacing-4));
}
.control-showcase__main { flex: 1; min-width: 0; }

@media (max-width: 1100px) {
  .control-showcase { flex-direction: column; }
  .config-card { width: 100%; }
}

.config-card {
  flex: 0 0 auto;
  width: 400px;
  align-self: flex-start;
  padding: var(--iflyv-spacing-4);
  background: var(--iflyv-bg-panel);
  border: 1px solid var(--iflyv-border-subtle);
  border-radius: var(--iflyv-radius-md);
}
.config-card__title {
  margin: 0 0 var(--iflyv-spacing-4);
  color: var(--iflyv-text-1);
  font: var(--iflyv-font-title-component);
}
</style>
