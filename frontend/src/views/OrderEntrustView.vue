<template>
  <section class="page-stack entrust-page">
    <div class="toolbar no-print">
      <div class="toolbar-left">
        <el-button :icon="ArrowLeft" @click="router.push(`/orders/${route.params.id}`)">返回订单</el-button>
        <strong>制版委托书</strong>
      </div>
      <div class="toolbar-left">
        <el-button :icon="Refresh" :loading="loading" @click="loadEntrust">刷新</el-button>
        <el-button v-if="sheet" type="primary" plain :icon="Grid" @click="scrollToLayoutEditor">Layout 排版图</el-button>
        <el-button v-if="sheet && canUpdateLayout" type="primary" :icon="Check" :loading="savingContent" @click="saveEntrustContent">保存表格内容</el-button>
        <el-button v-if="sheet && canUpdateLayout" :icon="Check" :loading="savingLayout" @click="saveLayout">保存版式</el-button>
        <el-button type="primary" :icon="Printer" :disabled="!sheet" @click="printSheet">导出 PDF / 打印</el-button>
      </div>
    </div>

    <el-card v-if="false" shadow="never" class="entrust-requirements no-print">
      <template #header>
        <div class="panel-title">
          <span>委托书要求备注</span>
          <el-button v-if="canUpdateLayout" type="primary" :icon="Check" :loading="savingRequirements" @click="saveRequirements">
            保存要求
          </el-button>
        </div>
      </template>
      <el-form :model="requirementForm" label-position="top" class="requirement-edit-form">
        <el-form-item label="Common Remarks" class="wide-field">
          <el-input v-model="requirementForm.common_remarks" />
        </el-form-item>
        <el-form-item label="Returns">
          <el-input v-model="requirementForm.returns" />
        </el-form-item>
        <el-form-item label="Archives">
          <el-input v-model="requirementForm.archives" />
        </el-form-item>
        <el-form-item label="Mark Line">
          <el-input v-model="requirementForm.mark_line" />
        </el-form-item>
        <el-form-item label="Test Line">
          <el-input v-model="requirementForm.test_line" />
        </el-form-item>
        <el-form-item label="Test Spot">
          <el-input v-model="requirementForm.test_spot" />
        </el-form-item>
        <el-form-item label="Computer Position">
          <el-input v-model="requirementForm.computer_position" />
        </el-form-item>
        <el-form-item label="Production Position">
          <el-input v-model="requirementForm.production_position" />
        </el-form-item>
        <el-form-item label="Computer Requirement" class="wide-field">
          <el-input v-model="requirementForm.computer_requirement" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Color Separation" class="wide-field">
          <el-input v-model="requirementForm.color_separation" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Engraving Requirement" class="wide-field">
          <el-input v-model="requirementForm.engraving_requirement" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Engraving Note" class="wide-field">
          <el-input v-model="requirementForm.engraving_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Proofing Requirement" class="wide-field">
          <el-input v-model="requirementForm.proofing_requirement" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Inspection Requirement" class="wide-field">
          <el-input v-model="requirementForm.inspection_requirement" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="sheet" shadow="never" class="layout-controls no-print">
      <template #header>
        <div class="panel-title">
          <span>委托书打印版式</span>
          <el-tag>{{ layoutStyleLabel }}</el-tag>
        </div>
      </template>
      <div v-if="false" class="layout-entry-banner">
        <strong>Layout 排版图编辑器</strong>
        <span>下方排版图按 Unit L、Unit W、Straight 自动计算 C、雕刻宽度和印刷宽度；点上方按钮可直接跳到编辑图。</span>
      </div>
      <el-form :model="layoutForm" label-position="top" class="layout-control-form">
        <el-form-item label="Title Type">
          <el-select v-model="layoutForm.title_mode">
            <el-option label="New Cylinder" value="new_cylinder" />
            <el-option label="Revision / Remake" value="old_cylinder" />
            <el-option label="Dechrome" value="dechrome" />
            <el-option label="Rework" value="rework" />
            <el-option label="Custom" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="Layout Style">
          <el-select v-model="layoutForm.diagram_style">
            <el-option label="Three Section" value="three_section" />
            <el-option label="Full Window" value="single_window" />
          </el-select>
        </el-form-item>
        <el-form-item label="Color Columns">
          <el-input-number v-model="layoutForm.color_columns" :min="4" :max="14" />
        </el-form-item>
        <div class="switch-row wide-field">
          <el-switch v-model="layoutForm.show_info_table" active-text="Main Info" />
          <el-switch v-model="layoutForm.show_color_table" active-text="Color Table" />
          <el-switch v-model="layoutForm.show_layout_diagram" active-text="Layout" />
        </div>
      </el-form>

      <div ref="layoutEditorRef" class="layout-editor">
        <div class="layout-tool-rail" role="toolbar" aria-label="Layout tools">
          <el-tooltip v-for="tool in layoutTools" :key="tool.type" :content="tool.label" placement="right">
            <el-button
              :class="{ active: activeTool === tool.type }"
              :title="tool.label"
              @click="addLayoutItem(tool)"
            >
              <span class="tool-svg" v-html="tool.svg"></span>
            </el-button>
          </el-tooltip>
        </div>
        <div class="layout-editor-main">
          <div class="layout-editor-fields layout-editor-fields-grouped">
            <div class="layout-side-fields">
              <div class="layout-param-column">
                <strong class="layout-column-title">Left</strong>
                <div class="layout-field field-with-toggle">
                  <span class="field-heading">
                    <span>Mark</span>
                    <el-checkbox class="detection-toggle" v-model="layoutForm.left_mark_enabled">Use</el-checkbox>
                    <el-button
                      class="fill-pattern-mini"
                      type="primary"
                      plain
                      :disabled="!canFillLeftSidePattern"
                      title="Fill left side pattern"
                      @click="fillSidePatternWithChoice('left')"
                    >
                      Fill Pattern
                    </el-button>
                  </span>
                  <el-input v-model="layoutForm.left_mark" />
                </div>
                <label>Empty Move <el-input v-model="layoutForm.empty_move" /></label>
                <div class="layout-field field-with-toggle">
                  <span class="field-heading">
                    <span>Detection</span>
                    <el-checkbox class="detection-toggle" v-model="layoutForm.left_detection_enabled">Use</el-checkbox>
                  </span>
                  <el-input v-model="layoutForm.left_detection" />
                </div>
                <label>Empty <el-input v-model="layoutForm.left_empty" /></label>
                <label>Color <el-input v-model="layoutForm.left_color" /></label>
                <label>Broaden <el-input v-model="layoutForm.left_broaden" /></label>
              </div>

              <div class="layout-param-column">
                <strong class="layout-column-title">Right</strong>
                <div class="layout-field field-with-toggle">
                  <span class="field-heading">
                    <span>Mark</span>
                    <el-checkbox class="detection-toggle" v-model="layoutForm.right_mark_enabled">Use</el-checkbox>
                    <el-button
                      class="fill-pattern-mini"
                      type="primary"
                      plain
                      :disabled="!canFillRightSidePattern"
                      title="Fill right side pattern"
                      @click="fillSidePatternWithChoice('right')"
                    >
                      Fill Pattern
                    </el-button>
                  </span>
                  <el-input v-model="layoutForm.right_mark" />
                </div>
                <label>Empty Move <el-input v-model="layoutForm.right_empty_move" /></label>
                <div class="layout-field field-with-toggle">
                  <span class="field-heading">
                    <span>Detection</span>
                    <el-checkbox class="detection-toggle" v-model="layoutForm.right_detection_enabled">Use</el-checkbox>
                  </span>
                  <el-input v-model="layoutForm.right_detection" />
                </div>
                <label>Empty <el-input v-model="layoutForm.right_empty" /></label>
                <label>Color <el-input v-model="layoutForm.right_color" /></label>
                <label>Broaden <el-input v-model="layoutForm.right_broaden" /></label>
              </div>
            </div>

            <div class="layout-common-fields">
              <strong class="layout-column-title">Common</strong>
              <label>Middle Broaden <el-input-number v-model="layoutForm.middle_broaden" :min="0" :precision="1" /></label>
              <label>Printing +mm <el-input v-model="layoutForm.printing_margin" /></label>
              <label>Columns <el-input-number v-model="layoutColumnsModel" :min="1" :max="24" /></label>
              <label>Rows <el-input-number v-model="layoutRowsModel" :min="1" :max="24" /></label>
              <label>Line W <el-input-number v-model="layoutForm.light_spot_width" :min="0" :max="12" /></label>
              <label>Pattern 1mm <el-input v-model="layoutForm.pattern_1mm_label" /></label>
              <label>Pattern 20mm <el-input v-model="layoutForm.pattern_20mm_label" /></label>
              <div class="layout-field field-with-toggle mid-mark-control">
                <span class="field-heading">
                  <span>Mid Mark</span>
                  <el-button
                    class="fill-pattern-mini"
                    type="primary"
                    plain
                    title="Fill center pattern"
                    @click="fillMidMarkPatternWithChoice"
                  >
                    Fill Pattern
                  </el-button>
                </span>
                <el-input v-model="layoutForm.mid_mark_value" placeholder="Mid Mark value" />
              </div>
            </div>

            <div class="layout-inline-options">
              <el-checkbox v-model="layoutForm.continuity">continuity</el-checkbox>
              <el-checkbox v-model="layoutForm.light_spot_upper_left">UL</el-checkbox>
              <el-checkbox v-model="layoutForm.light_spot_upper_right">UR</el-checkbox>
              <el-checkbox v-model="layoutForm.light_spot_lower_left">LL</el-checkbox>
              <el-checkbox v-model="layoutForm.light_spot_lower_right">LR</el-checkbox>
              <el-checkbox v-model="layoutForm.exclusive_use">Exclusive</el-checkbox>
              <el-checkbox v-model="layoutForm.left_self_mark">LSM</el-checkbox>
              <el-checkbox v-model="layoutForm.full_line">Full Line</el-checkbox>
            </div>
          </div>

          <div class="layout-blueprint">
            <div class="blueprint-top-line">
              <span>Left Mark <b>{{ value(layoutForm.left_mark, '') }}</b></span>
              <span>Empty Move <b>{{ value(layoutForm.empty_move, '') }}</b></span>
              <span>Left Detection <b>{{ formatNumber(leftDetectionWidth) || '' }}</b></span>
              <span>Left Color <b>{{ value(layoutForm.left_color || layoutForm.layout_color, '') }}</b></span>
              <span>Middle Broaden <b>{{ formatNumber(middleBroadenValue) || '' }}</b></span>
              <span>Right Color <b>{{ value(layoutForm.right_color || layoutForm.layout_color, '') }}</b></span>
              <span>Right Detection <b>{{ formatNumber(rightDetectionWidth) || '' }}</b></span>
              <span>Right Empty Move <b>{{ value(layoutForm.right_empty_move, '') }}</b></span>
              <span>Right Mark <b>{{ value(layoutForm.right_mark, '') }}</b></span>
            </div>
            <div class="blueprint-panel">
              <div class="blueprint-window" :style="layoutWindowStyle">
                <div
                  class="blueprint-section side-space side-box left-side-box has-mark-line"
                >
                  <span v-if="usesLeftDetection" class="layout-inner-line detection-line left" :style="leftDetectionLineStyle"></span>
                </div>
                <div class="blueprint-section center red middle-grid-section">
                  <div
                    class="middle-grid"
                    :style="middleGridStyle"
                  >
                    <span
                      v-for="cell in middleGridCells"
                      :key="cell.index"
                      class="middle-grid-cell"
                      :class="{ 'is-last-col': cell.lastCol, 'is-last-row': cell.lastRow }"
                    ></span>
                    <span class="layout-edge-ticks top">
                      <i v-for="tick in layoutTickMarks" :key="`editor-top-${tick}`" :style="{ left: `${tick}%` }"></i>
                    </span>
                    <span class="layout-edge-ticks bottom">
                      <i v-for="tick in layoutTickMarks" :key="`editor-bottom-${tick}`" :style="{ left: `${tick}%` }"></i>
                    </span>
                    <strong class="middle-grid-value">{{ cValueLabel }}</strong>
                    <span
                      v-for="spot in lightSpotMarkers"
                      :key="`editor-grid-${spot}`"
                      class="light-spot middle-light-spot"
                      :class="spot"
                    ></span>
                  </div>
                </div>
                <div
                  class="blueprint-section side-space side-box right-side-box has-mark-line"
                >
                  <span v-if="usesRightDetection" class="layout-inner-line detection-line right" :style="rightDetectionLineStyle"></span>
                </div>
                <span
                  v-for="label in layoutNearLineLabels"
                  :key="`editor-${label.key}`"
                  class="layout-near-label"
                  :class="label.className"
                  :style="label.style"
                >
                  {{ label.text }}
                </span>
                <div class="layout-dimension-arrow cir-dimension" aria-hidden="true">
                  <span class="dimension-line vertical"></span>
                  <strong>Cir. {{ cValueLabel }} mm</strong>
                </div>
                <div class="layout-dimension-arrow width-dimension" :style="layoutWidthDimensionStyle" aria-hidden="true">
                  <span class="dimension-line horizontal"></span>
                  <strong>Width: {{ lengthValueLabel }} mm</strong>
                </div>
                <div
                  ref="layoutCanvasRef"
                  class="layout-drawing-layer"
                  :class="{ 'is-selecting': activeTool === 'select' }"
                  @pointerdown="handleLayoutCanvasPointerDown"
                  @pointermove="handleLayoutPointerMove"
                  @pointerup="handleLayoutPointerUp"
                  @pointerleave="handleLayoutPointerUp"
                  @keydown="handleLayoutCanvasKeydown"
                  tabindex="0"
                >
                  <svg
                    class="layout-generated-layer"
                    viewBox="0 0 100 100"
                    preserveAspectRatio="none"
                    aria-hidden="true"
                    @pointerdown.stop="handleLayoutCanvasPointerDown"
                    @pointermove="handleLayoutPointerMove"
                    @pointerup="handleLayoutPointerUp"
                  >
                    <defs>
                      <marker id="layout-arrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
                        <path d="M0,0 L5,2.5 L0,5 Z" fill="#111827" />
                      </marker>
                    </defs>
                    <g
                      v-for="item in lineItems"
                      :key="`line-${item.id}`"
                      class="layout-svg-item"
                      :class="{ selected: item.id === selectedLayoutItemId }"
                      :data-id="item.id"
                      :transform="svgItemTransform(item)"
                      @pointerdown.stop="startLayoutDrag($event, item)"
                    >
                      <rect
                        class="layout-hit-box"
                        :x="lineHitBox(item).x"
                        :y="lineHitBox(item).y"
                        :width="lineHitBox(item).width"
                        :height="lineHitBox(item).height"
                        fill="rgba(17, 24, 39, 0.01)"
                        pointer-events="all"
                      />
                      <line
                        :x1="item.x"
                        :y1="item.y"
                        :x2="item.x2"
                        :y2="item.y2"
                        stroke="#111827"
                        :stroke-width="item.strokeWidth || layoutStrokeWidth"
                        :stroke-dasharray="item.dashed ? '4 3' : undefined"
                        :marker-start="item.arrowStart ? 'url(#layout-arrow)' : undefined"
                        :marker-end="item.arrow ? 'url(#layout-arrow)' : undefined"
                        stroke-linecap="square"
                        vector-effect="non-scaling-stroke"
                      />
                    </g>
                    <g
                      v-for="item in blockItems"
                      :key="`block-${item.id}`"
                      class="layout-svg-item"
                      :class="{ selected: item.id === selectedLayoutItemId }"
                      :data-id="item.id"
                      :transform="svgItemTransform(item)"
                      @pointerdown.stop="startLayoutDrag($event, item)"
                    >
                      <rect
                        :x="item.x"
                        :y="item.y"
                        :width="item.width || 5"
                        :height="item.height || 5"
                        fill="#111827"
                      />
                    </g>
                  </svg>
                  <span
                    v-for="item in markItems"
                    :key="item.id"
                    class="layout-added-item"
                    :class="[`layout-added-${item.type}`, { selected: item.id === selectedLayoutItemId }]"
                    :style="layoutItemStyle(item)"
                    :data-id="item.id"
                    @pointerdown.stop="startLayoutDrag($event, item)"
                  >
                    <svg
                      v-if="isSidePatternStack(item)"
                      class="layout-side-pattern-stack"
                      :class="`layout-side-pattern-stack-${item.type === 'side_pattern_mark_stack_right' ? 'right' : 'left'}`"
                      viewBox="0 0 52 148"
                      aria-hidden="true"
                    >
                      <path
                        :d="item.type === 'side_pattern_mark_stack_right'
                          ? 'M24 8 L24 86 M24 22 L40 40 L24 40 M12 68 L40 68'
                          : 'M28 8 L28 86 M28 22 L12 40 L28 40 M12 68 L40 68'"
                      />
                      <g class="layout-side-pattern-digits">
                        <circle cx="26" cy="98" r="4.9" /><text x="26" y="101">1</text>
                        <circle cx="26" cy="107" r="4.9" /><text x="26" y="110">2</text>
                        <circle cx="26" cy="116" r="4.9" /><text x="26" y="119">3</text>
                        <circle cx="26" cy="125" r="4.9" /><text x="26" y="128">4</text>
                        <circle cx="26" cy="134" r="4.9" /><text x="26" y="137">5</text>
                        <circle cx="26" cy="143" r="4.9" /><text x="26" y="146">6</text>
                      </g>
                    </svg>
                    <svg
                      v-else-if="isFlagItem(item)"
                      class="layout-flag-svg"
                      :class="`layout-flag-${item.type === 'right_flag_mark' ? 'right' : 'left'}`"
                      viewBox="0 0 28 56"
                      aria-hidden="true"
                    >
                      <path
                        :d="item.type === 'right_flag_mark'
                          ? 'M15 4 L15 52 M15 14 L24 28 L15 28 M6 36 L24 36'
                          : 'M13 4 L13 52 M13 14 L4 28 L13 28 M4 36 L22 36'"
                      />
                    </svg>
                    <template v-else>{{ item.symbol }}</template>
                  </span>
                  <div
                    v-if="selectedLayoutItem && !String(selectedLayoutItem.id).startsWith('auto-')"
                    class="layout-selection-box"
                    :style="selectionBoxStyle(selectedLayoutItem)"
                  >
                    <button
                      v-for="corner in resizeHandleCorners"
                      :key="corner"
                      type="button"
                      class="layout-transform-handle resize"
                      :class="corner"
                      :aria-label="`Resize ${corner}`"
                      @pointerdown.stop="startLayoutTransform($event, 'resize')"
                    ></button>
                    <button
                      type="button"
                      class="layout-transform-handle rotate"
                      aria-label="Rotate"
                      @pointerdown.stop="startLayoutTransform($event, 'rotate')"
                    ></button>
                    <button
                      type="button"
                      class="layout-transform-handle delete"
                      aria-label="Delete"
                      @pointerdown.stop
                      @click.stop="removeLayoutItem(selectedLayoutItem.id)"
                    >x</button>
                  </div>
                  <template v-if="selectedLayoutItem?.kind === 'line' && !String(selectedLayoutItem.id).startsWith('auto-')">
                    <button
                      type="button"
                      class="layout-line-endpoint-handle start"
                      :style="lineEndpointHandleStyle(selectedLayoutItem, 'start')"
                      aria-label="Drag start point"
                      @pointerdown.stop="startLayoutEndpointDrag($event, 'start')"
                    ></button>
                    <button
                      type="button"
                      class="layout-line-endpoint-handle end"
                      :style="lineEndpointHandleStyle(selectedLayoutItem, 'end')"
                      aria-label="Drag end point"
                      @pointerdown.stop="startLayoutEndpointDrag($event, 'end')"
                    ></button>
                  </template>
                </div>
              </div>
              <div class="layout-broaden-label left" :style="layoutLeftBroadenLabelStyle">LB {{ formatNumber(leftBroadenValue) || '' }} mm</div>
              <div class="layout-broaden-label right" :style="layoutRightBroadenLabelStyle">RB {{ formatNumber(rightBroadenValue) || '' }} mm</div>
            </div>
            <div class="blueprint-bottom-line">
              <span>Width of Engraving:</span>
              <strong class="red">{{ coreEngravingFormula }}</strong>
              <span>{{ coreEngravingWidthLabel }} mm</span>
            </div>
            <div class="blueprint-bottom-line engraving-width">
              <span>Engraving W:</span>
              <strong class="red">{{ engravingFormula }}</strong>
              <span>{{ engravingWidthLabel }} mm</span>
            </div>
            <div class="blueprint-bottom-line print-width">
              <span>Width of Printing:</span>
              <strong class="red">{{ printingFormula }}</strong>
              <span>{{ printingWidthLabel }} mm</span>
            </div>
          </div>
          <div class="layout-command-bar">
            <el-button type="primary" plain @click="saveLayoutTemplate">Save Template</el-button>
            <el-button plain @click="loadLayoutTemplate">Load Template</el-button>
            <el-button plain @click="archiveCurrentLayout">Save Layout</el-button>
            <el-button type="danger" plain :disabled="!selectedLayoutItem" @click="removeSelectedLayoutItem">Delete Selected</el-button>
            <el-button type="danger" plain :disabled="!layoutForm.layout_items.length" @click="wipeLayoutItems">Wipe</el-button>
          </div>
          <div v-if="selectedLayoutItem" class="layout-selected-editor">
            <strong>{{ selectedLayoutItem.label }}</strong>
            <label v-if="selectedLayoutItem.kind === 'mark' && !isScalableMark(selectedLayoutItem)">Text <el-input v-model="selectedLayoutItem.symbol" /></label>
            <label>X <el-input-number v-model="selectedLayoutItem.x" :min="0" :max="100" :precision="1" /></label>
            <label>Y <el-input-number v-model="selectedLayoutItem.y" :min="0" :max="100" :precision="1" /></label>
            <label v-if="selectedLayoutItem.kind === 'line'">X2 <el-input-number v-model="selectedLayoutItem.x2" :min="0" :max="100" :precision="1" /></label>
            <label v-if="selectedLayoutItem.kind === 'line'">Y2 <el-input-number v-model="selectedLayoutItem.y2" :min="0" :max="100" :precision="1" /></label>
            <label>Rotate <el-input-number v-model="selectedLayoutItem.rotation" :min="-180" :max="180" @change="syncSelectedGroupTransform('rotation')" /></label>
            <label>Scale <el-input-number v-model="selectedLayoutItem.scale" :min="0.1" :max="8" :step="0.05" :precision="2" @change="syncSelectedGroupTransform('scale')" /></label>
            <label v-if="isScalableMark(selectedLayoutItem)">Mark W <el-input-number v-model="selectedLayoutItem.scaleX" :min="0.1" :max="12" :step="0.05" :precision="2" @change="syncSelectedGroupTransform('scaleX')" /></label>
            <label v-if="isScalableMark(selectedLayoutItem)">Mark H <el-input-number v-model="selectedLayoutItem.scaleY" :min="0.1" :max="12" :step="0.05" :precision="2" @change="syncSelectedGroupTransform('scaleY')" /></label>
            <el-button type="danger" plain :icon="Minus" @click="removeLayoutItem(selectedLayoutItem.id)">Delete</el-button>
          </div>
          <div class="layout-item-list" v-if="layoutForm.layout_items.length">
            <span>Generated objects</span>
            <el-tag v-for="item in layoutForm.layout_items" :key="item.id" closable @close="removeLayoutItem(item.id)">
              {{ item.label }}
            </el-tag>
            <el-button size="small" plain :icon="Minus" @click="clearLayoutItems">Clear</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <div v-if="sheet" class="print-sheet">
      <datalist id="printing-method-options">
        <option value="inside" />
        <option value="outside" />
        <option value="inside+outside" />
        <option value="outside+inside" />
      </datalist>
      <h1 class="warrant-main-title">{{ entrustTitle }}</h1>
      <table class="warrant-table">
        <colgroup>
          <col class="warrant-label-col" />
          <col v-for="index in warrantColorIndexes" :key="`warrant-col-${index}`" />
          <col class="warrant-qty-col" />
        </colgroup>
        <tbody>
          <tr class="warrant-top-row">
            <td colspan="6" class="value strong">
              <span class="warrant-top-line">
                <span>Customer:</span>
                <strong>{{ value(sheet?.customer_name || detailRaw('customer_text')) }}</strong>
              </span>
            </td>
            <td colspan="4" class="value">
              <span class="warrant-top-line">
                <span>Sign:</span>
                <InlineCell field="sign_in_person" :fallback="details.sign_in_person" />
              </span>
            </td>
            <td colspan="5" class="value strong">
              <span class="warrant-top-line">
                <span>Samp.No:</span>
                <InlineCell field="sample_no" :fallback="sampleNoText" />
              </span>
            </td>
          </tr>
          <tr class="warrant-info-row">
            <th>Cyl.No.</th>
            <td colspan="3" class="value red"><InlineCell field="cylinder_id" :fallback="primaryCylinderNoText" /></td>
            <th>Product<br />Name</th>
            <td colspan="4" class="value red"><InlineCell field="product_name" :fallback="details.product_name || order.product_summary" /></td>
            <th>Printing<br />Method</th>
            <td colspan="2" class="value red"><InlineCell field="printing_method" :fallback="details.printing_method" /></td>
            <th>Material<br />Type</th>
            <td colspan="2" class="value red"><InlineCell field="material_new" :fallback="materialNewText" /></td>
          </tr>
          <tr class="warrant-info-row">
            <th>U.L</th>
            <td class="value red"><InlineCell field="unit_l" :fallback="details.unit_l || details.l_value" /></td>
            <th>NC</th>
            <td class="value red"><InlineCell field="straight" :fallback="details.straight" /></td>
            <th>U.W</th>
            <td class="value red"><InlineCell field="unit_w" :fallback="details.unit_w || details.width" /></td>
            <th>NC</th>
            <td colspan="2" class="value red"><InlineCell field="crossway" :fallback="details.crossway" /></td>
            <th>Bag Type</th>
            <td colspan="2" class="value red"><InlineCell field="bag_type" :fallback="details.bag_type" /></td>
            <th>New</th>
            <td colspan="2" class="value red"><InlineCell field="material_new" :fallback="materialNewText" /></td>
          </tr>
          <tr class="warrant-info-row">
            <th>Cir.</th>
            <td colspan="3" class="value red"><InlineCell field="c_value" :fallback="cValueLabel" /></td>
            <th>Length</th>
            <td colspan="2" class="value red"><InlineCell field="l_value" :fallback="lengthValueLabel" /></td>
            <th>Dia.</th>
            <td class="value red">{{ diaText }}</td>
            <th>Increace</th>
            <td colspan="2" class="value red"><InlineCell field="increase" :fallback="details.increase" /></td>
            <th>Old</th>
            <td colspan="2" class="value red"><InlineCell field="original_no" :fallback="oldCylinderNoText" /></td>
          </tr>
          <tr class="warrant-info-row">
            <th>Flange<br />Width</th>
            <td colspan="3" class="value red"><InlineCell field="width" :fallback="widthText" /></td>
            <th>Flange<br />Slope</th>
            <td colspan="2" class="value red"><InlineCell field="slope" :fallback="details.slope" /></td>
            <th>Flange<br />Hole</th>
            <td class="value red"><InlineCell field="hole" :fallback="details.hole" /></td>
            <th>Keyway</th>
            <td colspan="2" class="value red"><InlineCell field="key_way" :fallback="details.key_way" /></td>
            <th>Printing<br />Material</th>
            <td colspan="2" class="value red"><InlineCell field="printing_material" :fallback="details.printing_material" /></td>
          </tr>
          <tr class="warrant-info-row">
            <th>Markline</th>
            <td colspan="3" class="value red"><InlineCell field="mark_line" :fallback="details.mark_line" /></td>
            <th>Test line</th>
            <td colspan="2" class="value red"><InlineCell field="test_line" :fallback="details.test_line" /></td>
            <th>Test spot</th>
            <td class="value red"><InlineCell field="test_spot" :fallback="details.test_spot" /></td>
            <th>Remarks</th>
            <td colspan="5" class="value red"><InlineCell field="common_remarks" :fallback="details.common_remarks || details.printings" multiline /></td>
          </tr>

          <template v-if="layoutForm.show_color_table">
            <tr>
              <th>Color NO</th>
              <th v-for="index in warrantColorIndexes" :key="`color-no-${index}`">{{ defaultColorNo(index - 1) }}</th>
              <th>QTY</th>
            </tr>
            <tr>
              <th>PrintColor</th>
              <td v-for="index in warrantColorIndexes" :key="`print-color-${index}`" class="value red">
                <InlineColorCell :row-index="index - 1" field="print_color" :fallback="colorRows[index - 1]?.print_color" />
              </td>
              <td class="value red">{{ totalColorQty }}</td>
            </tr>
            <tr>
              <th>QTY</th>
              <td v-for="index in warrantColorIndexes" :key="`qty-${index}`" class="value red">
                <InlineColorCell :row-index="index - 1" field="qty" :fallback="colorQtyFallback(index - 1)" />
              </td>
              <td></td>
            </tr>
            <tr>
              <th>Real Dia</th>
              <td v-for="index in warrantColorIndexes" :key="`real-dia-${index}`" class="value red">
                <InlineColorCell :row-index="index - 1" field="real_dia" :fallback="colorDiaFallback(index - 1)" />
              </td>
              <td></td>
            </tr>
            <tr>
              <th>Print Method</th>
              <td v-for="index in warrantColorIndexes" :key="`print-method-${index}`" class="value red">
                <InlineColorCell :row-index="index - 1" field="printing_method" :fallback="printMethodFallback(index - 1)" />
              </td>
              <td></td>
            </tr>
          </template>

          <template v-if="layoutForm.show_layout_diagram">
            <tr class="warrant-layout-title">
              <th :colspan="warrantColumnSpan">Layout</th>
            </tr>
            <tr>
              <td :colspan="warrantColumnSpan" class="warrant-layout-cell">
                <table v-if="layoutForm.diagram_style === 'text_only'" class="layout-note-table">
                  <tbody>
                    <tr>
                      <th>Layout Requirement</th>
                      <td class="red">{{ value(layoutForm.custom_note || layoutForm.bottom_note || details.computer_requirement) }}</td>
                    </tr>
                  </tbody>
                </table>
                <div v-else class="layout-box warrant-layout-box" :class="`layout-${layoutForm.diagram_style}`">
                  <div class="layout-core">
                    <div class="layout-top">
                      <span
                        v-for="guide in printLayoutTopGuides"
                        :key="guide.key"
                        class="layout-top-guide"
                        :class="guide.className"
                        :style="guide.style"
                      >
                        {{ guide.text }}
                      </span>
                    </div>
                    <div class="layout-window" :style="layoutWindowStyle">
                      <template v-if="layoutForm.diagram_style === 'single_window'">
                        <div class="layout-section layout-section-full red">
                          {{ value(layoutForm.center_label || layoutForm.custom_note || cValueLabel, 'Layout') }}
                        </div>
                      </template>
                      <template v-else>
                        <div
                          class="layout-section side-space side-box left-side-box has-mark-line"
                        >
                          <span v-if="usesLeftDetection" class="layout-inner-line detection-line left" :style="leftDetectionLineStyle"></span>
                        </div>
                        <div class="layout-section red middle-print-section">
                          <div class="middle-grid print-grid" :style="middleGridStyle">
                            <span
                              v-for="cell in middleGridCells"
                              :key="cell.index"
                              class="middle-grid-cell"
                              :class="{ 'is-last-col': cell.lastCol, 'is-last-row': cell.lastRow }"
                            ></span>
                            <span class="layout-edge-ticks top">
                              <i v-for="tick in layoutTickMarks" :key="`print-top-${tick}`" :style="{ left: `${tick}%` }"></i>
                            </span>
                            <span class="layout-edge-ticks bottom">
                              <i v-for="tick in layoutTickMarks" :key="`print-bottom-${tick}`" :style="{ left: `${tick}%` }"></i>
                            </span>
                            <strong class="middle-grid-value">{{ value(layoutForm.center_label, cValueLabel) }}</strong>
                            <span
                              v-for="spot in lightSpotMarkers"
                              :key="`print-grid-${spot}`"
                              class="light-spot middle-light-spot"
                              :class="spot"
                            ></span>
                          </div>
                        </div>
                        <div
                          class="layout-section side-space side-box right-side-box has-mark-line"
                        >
                          <span v-if="usesRightDetection" class="layout-inner-line detection-line right" :style="rightDetectionLineStyle"></span>
                        </div>
                        <span
                          v-for="label in layoutNearLineLabels"
                          :key="`print-${label.key}`"
                          class="layout-near-label"
                          :class="label.className"
                          :style="label.style"
                        >
                          {{ label.text }}
                        </span>
                        <div class="layout-dimension-arrow cir-dimension" aria-hidden="true">
                          <span class="dimension-line vertical"></span>
                          <strong>Cir. {{ cValueLabel }} mm</strong>
                        </div>
                        <div class="layout-dimension-arrow width-dimension" :style="layoutWidthDimensionStyle" aria-hidden="true">
                          <span class="dimension-line horizontal"></span>
                          <strong>Width: {{ lengthValueLabel }} mm</strong>
                        </div>
                        <div class="layout-broaden-label left" :style="layoutLeftBroadenLabelStyle">LB {{ formatNumber(leftBroadenValue) || '' }} mm</div>
                        <div class="layout-broaden-label right" :style="layoutRightBroadenLabelStyle">RB {{ formatNumber(rightBroadenValue) || '' }} mm</div>
                        <div class="layout-drawing-layer print-drawing-layer">
                          <svg class="layout-generated-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                            <defs>
                              <marker id="layout-print-arrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
                                <path d="M0,0 L5,2.5 L0,5 Z" fill="#111827" />
                              </marker>
                            </defs>
                            <g
                              v-for="item in lineItems"
                              :key="`warrant-line-${item.id}`"
                              :transform="svgItemTransform(item)"
                            >
                              <line
                                :x1="item.x"
                                :y1="item.y"
                                :x2="item.x2"
                                :y2="item.y2"
                                stroke="#111827"
                                :stroke-width="item.strokeWidth || layoutStrokeWidth"
                                :stroke-dasharray="item.dashed ? '4 3' : undefined"
                                :marker-start="item.arrowStart ? 'url(#layout-print-arrow)' : undefined"
                                :marker-end="item.arrow ? 'url(#layout-print-arrow)' : undefined"
                                stroke-linecap="square"
                                vector-effect="non-scaling-stroke"
                              />
                            </g>
                            <g
                              v-for="item in blockItems"
                              :key="`warrant-block-${item.id}`"
                              :transform="svgItemTransform(item)"
                            >
                              <rect
                                :x="item.x"
                                :y="item.y"
                                :width="item.width || 5"
                                :height="item.height || 5"
                                fill="#111827"
                              />
                            </g>
                          </svg>
                          <span
                            v-for="item in markItems"
                            :key="item.id"
                            class="layout-added-item"
                          :class="`layout-added-${item.type}`"
                          :style="layoutItemStyle(item)"
                        >
                            <svg
                              v-if="isSidePatternStack(item)"
                              class="layout-side-pattern-stack"
                              :class="`layout-side-pattern-stack-${item.type === 'side_pattern_mark_stack_right' ? 'right' : 'left'}`"
                              viewBox="0 0 52 148"
                              aria-hidden="true"
                            >
                              <path
                                :d="item.type === 'side_pattern_mark_stack_right'
                                  ? 'M24 8 L24 86 M24 22 L40 40 L24 40 M12 68 L40 68'
                                  : 'M28 8 L28 86 M28 22 L12 40 L28 40 M12 68 L40 68'"
                              />
                              <g class="layout-side-pattern-digits">
                                <circle cx="26" cy="98" r="4.9" /><text x="26" y="101">1</text>
                                <circle cx="26" cy="107" r="4.9" /><text x="26" y="110">2</text>
                                <circle cx="26" cy="116" r="4.9" /><text x="26" y="119">3</text>
                                <circle cx="26" cy="125" r="4.9" /><text x="26" y="128">4</text>
                                <circle cx="26" cy="134" r="4.9" /><text x="26" y="137">5</text>
                                <circle cx="26" cy="143" r="4.9" /><text x="26" y="146">6</text>
                              </g>
                            </svg>
                            <svg
                              v-else-if="isFlagItem(item)"
                              class="layout-flag-svg"
                              :class="`layout-flag-${item.type === 'right_flag_mark' ? 'right' : 'left'}`"
                              viewBox="0 0 28 56"
                              aria-hidden="true"
                            >
                              <path
                                :d="item.type === 'right_flag_mark'
                                  ? 'M15 4 L15 52 M15 14 L24 28 L15 28 M6 36 L24 36'
                                  : 'M13 4 L13 52 M13 14 L4 28 L13 28 M4 36 L22 36'"
                              />
                            </svg>
                            <template v-else>{{ item.symbol }}</template>
                          </span>
                        </div>
                      </template>
                    </div>
                  </div>
                  <div class="layout-formula-table">
                    <div>
                      <span>Width of Engraving</span>
                      <strong class="red">{{ coreEngravingFormula }}</strong>
                      <span>{{ coreEngravingWidthLabel }} mm</span>
                    </div>
                    <div>
                      <span>Engraving W</span>
                      <strong class="red">{{ engravingFormula }}</strong>
                      <span>{{ engravingWidthLabel }} mm</span>
                    </div>
                    <div>
                      <span>Width of Printing</span>
                      <strong class="red">{{ printingFormula }}</strong>
                      <span>{{ printingWidthLabel }} mm</span>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </template>

          <tr>
            <th colspan="2">Order Date:</th>
            <td colspan="4" class="value red">{{ orderDateText }}</td>
            <th colspan="2">Salesman:</th>
            <td colspan="3" class="value red"><InlineCell field="salesman" :fallback="salesmanText" /></td>
            <th>Lister:</th>
            <td colspan="3" class="value red"><InlineCell field="lister" :fallback="listerText" /></td>
          </tr>
          <tr>
            <th colspan="2">Old Cyl.No.</th>
            <td colspan="4" class="value red"><InlineCell field="original_no" :fallback="oldCylinderNoText" /></td>
            <th colspan="2">NO:</th>
            <td colspan="3" class="value">{{ order.order_no }}</td>
            <th>Remark</th>
            <td colspan="3" class="value red"><InlineCell field="common_remarks" :fallback="details.common_remarks" /></td>
          </tr>
        </tbody>
      </table>

    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onMounted, reactive, ref, watch } from 'vue'
import type { PropType } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Check, Grid, Minus, Printer, Refresh } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { ColorRow, EntrustLayoutSettings, EntrustSheet, PlateDetails, PlateValue, SalesOrder } from '../api/types'
import { hasPermission } from '../stores/session'

const route = useRoute()
const router = useRouter()
const sheet = ref<EntrustSheet | null>(null)
const loading = ref(false)
const savingLayout = ref(false)
const savingRequirements = ref(false)
const savingContent = ref(false)
const layoutEditorRef = ref<HTMLElement | null>(null)
const layoutCanvasRef = ref<HTMLElement | null>(null)
const selectedLayoutItemId = ref('')
const resizeHandleCorners = ['top-left', 'top-right', 'bottom-left', 'bottom-right']
const draggingLayoutItem = ref<{
  id: string
  mode: 'move' | 'resize' | 'rotate' | 'line-start' | 'line-end' | 'draw-block' | 'draw-cross'
  lastX: number
  lastY: number
  startX: number
  startY: number
  centerX: number
  centerY: number
  startScale: number
  startScaleX: number
  startScaleY: number
  startRotation: number
  startItems?: Array<{
    id: string
    kind: LayoutItem['kind']
    x: number
    y: number
    x2?: number
    y2?: number
    width?: number
    height?: number
    rotation: number
  }>
} | null>(null)

const requirementKeys = [
  'common_remarks',
  'returns',
  'archives',
  'inspection_requirement',
  'mark_line',
  'test_line',
  'test_spot',
  'computer_position',
  'production_position',
  'engraving_requirement',
  'proofing_requirement',
  'computer_requirement',
  'color_separation',
  'engraving_note'
] as const
type RequirementKey = (typeof requirementKeys)[number]
const requirementForm = reactive<Record<RequirementKey, string>>(
  Object.fromEntries(requirementKeys.map((key) => [key, ''])) as Record<RequirementKey, string>
)

const editableDetailKeys = [
  'cylinder_id',
  'no',
  'sign_in_person',
  'sample_no',
  'product_name',
  'printing_material',
  'printing_method',
  'material_model',
  'cylinder_model',
  'bag_type',
  'material_new',
  'new_material',
  'l_value',
  'increase',
  'slope',
  'key_way',
  'hor_ver',
  'original_no',
  'derived_source_cylinder_no',
  'rework_source_cylinder_no',
  'old_cyl_no',
  'test_line',
  'dia',
  'hole',
  'test_spot',
  'printings',
  'unit',
  'returns',
  'c_value',
  'width',
  'mark_line',
  'salesman',
  'lister',
  'archives',
  'flange',
  'set_type',
  'unit_l',
  'unit_w',
  'straight',
  'crossway',
  'order_datetime',
  'computer_requirement',
  'color_separation',
  'engraving_requirement',
  'engraving_note',
  'proofing_requirement',
  'inspection_requirement',
  'computer_position',
  'production_position',
  'mark_test_position',
  'common_remarks'
] as const
const editableColorKeys = ['color_no', 'print_color', 'qty', 'dia', 'real_dia', 'public_no', 'printing_method', 'remarks'] as const
const maxInlineColorRows = 14
const inlineDetails = reactive<Record<string, string>>({})
const inlineColorRows = ref<Array<Record<string, string>>>([])

interface LayoutItem {
  id: string
  kind: 'line' | 'mark' | 'block'
  type: string
  label: string
  symbol: string
  x: number
  y: number
  x2?: number
  y2?: number
  width?: number
  height?: number
  strokeWidth?: number
  dashed?: boolean
  arrow?: boolean
  arrowStart?: boolean
  rotation?: number
  scale?: number
  scaleX?: number
  scaleY?: number
  groupId?: string
}

interface LayoutTool {
  type: string
  label: string
  kind: LayoutItem['kind']
  symbol: string
  svg: string
  defaultX: number
  defaultY: number
  defaultX2?: number
  defaultY2?: number
  width?: number
  height?: number
  strokeWidth?: number
  dashed?: boolean
  arrow?: boolean
  arrowStart?: boolean
  group?: 'cross' | 'parallel' | 'cornerLeft' | 'cornerBottom' | 'teeLine'
}

interface LayoutLineLabel {
  key: string
  text: string
  className?: string
  style: Record<string, string>
}

interface LayoutTopGuide {
  key: string
  text: string
  className?: string
  style: Record<string, string>
}

interface EntrustLayoutForm {
  title_mode: string
  diagram_style: string
  color_columns: number
  show_info_table: boolean
  show_color_table: boolean
  show_layout_diagram: boolean
  show_requirements: boolean
  left_label: string
  center_label: string
  right_label: string
  top_note: string
  bottom_note: string
  width_label: string
  custom_note: string
  left_mark: string
  empty_move: string
  left_detection: string
  left_empty: string
  empty_color_move: string
  layout_color: string
  left_color: string
  right_color: string
  left_broaden: string
  middle_broaden: number
  right_move: string
  right_mark: string
  right_empty_move: string
  right_detection: string
  right_empty: string
  right_broaden: string
  printing_width: string
  printing_margin: string
  continuity: boolean
  light_spot_horizontal: number
  light_spot_vertical: number
  light_spot_width: number
  pattern_1mm_label: string
  pattern_20mm_label: string
  light_spot_upper_left: boolean
  light_spot_upper_right: boolean
  light_spot_lower_left: boolean
  light_spot_lower_right: boolean
  left_mark_enabled: boolean
  right_mark_enabled: boolean
  left_detection_enabled: boolean
  right_detection_enabled: boolean
  exclusive_use: boolean
  mid_mark: boolean
  mid_mark_value: string
  left_self_mark: boolean
  right_self_mark: boolean
  full_line: boolean
  full_line_width: string
  layout_items: LayoutItem[]
}

const layoutForm = reactive<EntrustLayoutForm>({
  title_mode: 'new_cylinder',
  diagram_style: 'three_section',
  color_columns: 13,
  show_info_table: true,
  show_color_table: true,
  show_layout_diagram: true,
  show_requirements: false,
  left_label: '',
  center_label: '',
  right_label: '',
  top_note: '',
  bottom_note: '',
  width_label: '',
  custom_note: '',
  left_mark: '',
  empty_move: '',
  left_detection: '',
  left_empty: '',
  empty_color_move: '',
  layout_color: '',
  left_color: '',
  right_color: '',
  left_broaden: '',
  middle_broaden: 0,
  right_move: '',
  right_mark: '',
  right_empty_move: '',
  right_detection: '',
  right_empty: '',
  right_broaden: '',
  printing_width: '',
  printing_margin: '',
  continuity: false,
  light_spot_horizontal: 1,
  light_spot_vertical: 1,
  light_spot_width: 0,
  pattern_1mm_label: '',
  pattern_20mm_label: '',
  light_spot_upper_left: false,
  light_spot_upper_right: false,
  light_spot_lower_left: false,
  light_spot_lower_right: false,
  left_mark_enabled: true,
  right_mark_enabled: true,
  left_detection_enabled: false,
  right_detection_enabled: false,
  exclusive_use: false,
  mid_mark: false,
  mid_mark_value: '',
  left_self_mark: false,
  right_self_mark: false,
  full_line: false,
  full_line_width: '',
  layout_items: []
})

const layoutColumnsModel = computed({
  get: () => clampInteger(layoutForm.light_spot_horizontal, 1, 24, 1),
  set: (input: number | undefined) => {
    const value = clampInteger(input, 1, 24, 1)
    layoutForm.light_spot_horizontal = value
    inlineDetails.straight = String(value)
    syncInlineDerivedFields('straight')
  }
})
const layoutRowsModel = computed({
  get: () => clampInteger(layoutForm.light_spot_vertical, 1, 24, 1),
  set: (input: number | undefined) => {
    const value = clampInteger(input, 1, 24, 1)
    layoutForm.light_spot_vertical = value
    inlineDetails.crossway = String(value)
  }
})

watch(
  () => [layoutForm.pattern_1mm_label, layoutForm.pattern_20mm_label],
  () => syncSidePatternTextLabels()
)

const layoutStrokeWidth = 2
const activeTool = ref('select')
interface StoredLayoutTemplate {
  id?: string
  name: string
  template_type?: 'template' | 'archive'
  created_at?: string
  order_no?: string
  settings: EntrustLayoutSettings & { layout_items?: LayoutItem[] }
}

const toolSvg = {
  select: '<svg viewBox="0 0 32 32"><path d="M7 4 L25 16 L17 18 L21 29 L17 30 L13 20 L7 25 Z"/></svg>',
  text: '<svg viewBox="0 0 32 32"><text x="9" y="25" font-size="24" font-weight="800" fill="currentColor">T</text></svg>',
  arrowLeft: '<svg viewBox="0 0 32 32"><line x1="26" y1="16" x2="7" y2="16"/><path d="M12 10 L6 16 L12 22"/></svg>',
  arrowRight: '<svg viewBox="0 0 32 32"><line x1="6" y1="16" x2="25" y2="16"/><path d="M20 10 L26 16 L20 22"/></svg>',
  arrowUp: '<svg viewBox="0 0 32 32"><line x1="16" y1="26" x2="16" y2="7"/><path d="M10 12 L16 6 L22 12"/></svg>',
  arrowDown: '<svg viewBox="0 0 32 32"><line x1="16" y1="6" x2="16" y2="25"/><path d="M10 20 L16 26 L22 20"/></svg>',
  arrowUpLeft: '<svg viewBox="0 0 32 32"><line x1="24" y1="24" x2="9" y2="9"/><path d="M9 17 L9 9 L17 9"/></svg>',
  arrowUpRight: '<svg viewBox="0 0 32 32"><line x1="8" y1="24" x2="23" y2="9"/><path d="M15 9 L23 9 L23 17"/></svg>',
  arrowDownLeft: '<svg viewBox="0 0 32 32"><line x1="24" y1="8" x2="9" y2="23"/><path d="M9 15 L9 23 L17 23"/></svg>',
  arrowDownRight: '<svg viewBox="0 0 32 32"><line x1="8" y1="8" x2="23" y2="23"/><path d="M15 23 L23 23 L23 15"/></svg>',
  horizontal: '<svg viewBox="0 0 32 32"><line x1="5" y1="16" x2="27" y2="16"/></svg>',
  vertical: '<svg viewBox="0 0 32 32"><line x1="16" y1="5" x2="16" y2="27"/></svg>',
  doubleHorizontal: '<svg viewBox="0 0 32 32"><line x1="7" y1="16" x2="25" y2="16"/><path d="M11 10 L5 16 L11 22"/><path d="M21 10 L27 16 L21 22"/></svg>',
  cross: '<svg viewBox="0 0 32 32"><line x1="5" y1="16" x2="27" y2="16"/><line x1="16" y1="5" x2="16" y2="27"/></svg>',
  flagLeft: '<svg viewBox="0 0 32 32"><path d="M17 4 L17 28 M17 9 L8 17 L17 17 M8 22 L24 22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  flagRight: '<svg viewBox="0 0 32 32"><path d="M15 4 L15 28 M15 9 L24 17 L15 17 M8 22 L24 22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  block: '<svg viewBox="0 0 32 32"><rect x="5" y="13" width="22" height="6" fill="currentColor" stroke="none"/></svg>',
  parallel: '<svg viewBox="0 0 32 32"><line x1="8" y1="9" x2="24" y2="9"/><line x1="8" y1="16" x2="24" y2="16"/><line x1="8" y1="23" x2="24" y2="23"/></svg>',
  cornerLeft: '<svg viewBox="0 0 32 32"><line x1="12" y1="6" x2="12" y2="26"/><line x1="12" y1="16" x2="26" y2="16"/></svg>',
  cornerBottom: '<svg viewBox="0 0 32 32"><line x1="7" y1="22" x2="25" y2="22"/><line x1="16" y1="8" x2="16" y2="22"/></svg>',
  dots: '<svg viewBox="0 0 32 32"><text x="16" y="8" text-anchor="middle" font-size="7" font-weight="800" fill="currentColor" stroke="none">1</text><text x="16" y="15" text-anchor="middle" font-size="7" font-weight="800" fill="currentColor" stroke="none">2</text><text x="16" y="22" text-anchor="middle" font-size="7" font-weight="800" fill="currentColor" stroke="none">3</text><text x="16" y="29" text-anchor="middle" font-size="7" font-weight="800" fill="currentColor" stroke="none">4</text></svg>',
  tee: '<svg viewBox="0 0 32 32"><line x1="12" y1="5" x2="12" y2="27"/><line x1="12" y1="16" x2="25" y2="16"/></svg>',
  emptyBox: '<svg viewBox="0 0 32 32"><rect x="7" y="7" width="18" height="18"/></svg>',
  dashed: '<svg viewBox="0 0 32 32"><line x1="5" y1="16" x2="27" y2="16" stroke-dasharray="4 3"/></svg>',
  inspection: '<svg viewBox="0 0 32 32"><line x1="10" y1="4" x2="10" y2="28" stroke-width="4"/><text x="22" y="8" text-anchor="middle" font-size="8" font-family="Arial, sans-serif" font-weight="800" fill="currentColor" stroke="none">检</text><text x="22" y="17" text-anchor="middle" font-size="8" font-family="Arial, sans-serif" font-weight="800" fill="currentColor" stroke="none">测</text><text x="22" y="26" text-anchor="middle" font-size="8" font-family="Arial, sans-serif" font-weight="800" fill="currentColor" stroke="none">线</text></svg>',
  target: '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="12"/><line x1="16" y1="4" x2="16" y2="28"/><line x1="4" y1="16" x2="28" y2="16"/></svg>'
}
const layoutTools: LayoutTool[] = [
  { type: 'select', label: 'Select / move', kind: 'mark', symbol: '', svg: toolSvg.select, defaultX: 50, defaultY: 50 },
  { type: 'text', label: 'Text', kind: 'mark', symbol: 'T', svg: toolSvg.text, defaultX: 50, defaultY: 38 },
  { type: 'arrow_left', label: 'Left arrow line', kind: 'line', symbol: '<-', svg: toolSvg.arrowLeft, defaultX: 66, defaultY: 50, defaultX2: 34, defaultY2: 50, strokeWidth: 2, arrow: true },
  { type: 'arrow_right', label: 'Right arrow line', kind: 'line', symbol: '->', svg: toolSvg.arrowRight, defaultX: 34, defaultY: 50, defaultX2: 66, defaultY2: 50, strokeWidth: 2, arrow: true },
  { type: 'arrow_up', label: 'Up arrow line', kind: 'line', symbol: '^', svg: toolSvg.arrowUp, defaultX: 50, defaultY: 66, defaultX2: 50, defaultY2: 34, strokeWidth: 2, arrow: true },
  { type: 'arrow_down', label: 'Down arrow line', kind: 'line', symbol: 'v', svg: toolSvg.arrowDown, defaultX: 50, defaultY: 34, defaultX2: 50, defaultY2: 66, strokeWidth: 2, arrow: true },
  { type: 'arrow_up_left', label: 'Up-left arrow', kind: 'line', symbol: '↖', svg: toolSvg.arrowUpLeft, defaultX: 62, defaultY: 62, defaultX2: 38, defaultY2: 38, strokeWidth: 2, arrow: true },
  { type: 'arrow_up_right', label: 'Up-right arrow', kind: 'line', symbol: '↗', svg: toolSvg.arrowUpRight, defaultX: 38, defaultY: 62, defaultX2: 62, defaultY2: 38, strokeWidth: 2, arrow: true },
  { type: 'arrow_down_left', label: 'Down-left arrow', kind: 'line', symbol: '↙', svg: toolSvg.arrowDownLeft, defaultX: 62, defaultY: 38, defaultX2: 38, defaultY2: 62, strokeWidth: 2, arrow: true },
  { type: 'arrow_down_right', label: 'Down-right arrow', kind: 'line', symbol: '↘', svg: toolSvg.arrowDownRight, defaultX: 38, defaultY: 38, defaultX2: 62, defaultY2: 62, strokeWidth: 2, arrow: true },
  { type: 'double_arrow', label: 'Double arrow line', kind: 'line', symbol: '↔', svg: toolSvg.doubleHorizontal, defaultX: 34, defaultY: 50, defaultX2: 66, defaultY2: 50, strokeWidth: 2, arrow: true, arrowStart: true },
  { type: 'cross', label: 'Cross line', kind: 'line', symbol: '+', svg: toolSvg.cross, defaultX: 50, defaultY: 50, group: 'cross', strokeWidth: 2 },
  { type: 'left_flag_mark', label: 'Left flag mark', kind: 'mark', symbol: '', svg: toolSvg.flagLeft, defaultX: 16, defaultY: 48 },
  { type: 'right_flag_mark', label: 'Right flag mark', kind: 'mark', symbol: '', svg: toolSvg.flagRight, defaultX: 84, defaultY: 48 },
  { type: 'horizontal_line', label: 'Horizontal line', kind: 'line', symbol: '-', svg: toolSvg.horizontal, defaultX: 28, defaultY: 50, defaultX2: 72, defaultY2: 50, strokeWidth: 2 },
  { type: 'vertical_line', label: 'Vertical line', kind: 'line', symbol: '|', svg: toolSvg.vertical, defaultX: 50, defaultY: 28, defaultX2: 50, defaultY2: 72, strokeWidth: 2 },
  { type: 'solid_block', label: 'Black bar', kind: 'block', symbol: '[]', svg: toolSvg.block, defaultX: 20, defaultY: 18, width: 10, height: 2 },
  { type: 'parallel_lines', label: 'Parallel lines', kind: 'line', symbol: '|||', svg: toolSvg.parallel, defaultX: 24, defaultY: 70, group: 'parallel', strokeWidth: 1.8 },
  { type: 'corner_left', label: 'Left corner line', kind: 'line', symbol: '|-', svg: toolSvg.cornerLeft, defaultX: 18, defaultY: 52, group: 'cornerLeft', strokeWidth: 2 },
  { type: 'corner_bottom', label: 'Bottom corner line', kind: 'line', symbol: '_|', svg: toolSvg.cornerBottom, defaultX: 50, defaultY: 82, group: 'cornerBottom', strokeWidth: 2 },
  { type: 'dot_column', label: 'Number marks 1-4', kind: 'mark', symbol: '1\n2\n3\n4', svg: toolSvg.dots, defaultX: 18, defaultY: 58 },
  { type: 'tee_line', label: 'T line', kind: 'line', symbol: 'T', svg: toolSvg.tee, defaultX: 50, defaultY: 50, group: 'teeLine', strokeWidth: 2 },
  { type: 'empty_box', label: 'Empty box', kind: 'mark', symbol: '□', svg: toolSvg.emptyBox, defaultX: 24, defaultY: 24 },
  { type: 'dashed_line', label: 'Dashed line', kind: 'line', symbol: '---', svg: toolSvg.dashed, defaultX: 28, defaultY: 74, defaultX2: 72, defaultY2: 74, strokeWidth: 1.8, dashed: true },
  { type: 'inspection_line', label: 'Inspection line', kind: 'line', symbol: '|', svg: toolSvg.inspection, defaultX: 50, defaultY: 22, defaultX2: 50, defaultY2: 78, strokeWidth: 3 },
  { type: 'target_mark', label: 'Target mark', kind: 'mark', symbol: '⊕', svg: toolSvg.target, defaultX: 50, defaultY: 50 }
]

const order = computed(() => sheet.value!.order)
const details = computed<PlateDetails>(() => sheet.value?.order.plate_details || {})
const colorRows = computed<ColorRow[]>(() => sheet.value?.order.color_rows || [])
const firstColor = computed<ColorRow>(() => colorRows.value[0] || {})
const canUpdateLayout = computed(() => hasPermission('order:update'))
const warrantColorIndexes = computed(() => Array.from({ length: 13 }, (_, index) => index + 1))
const warrantColumnSpan = computed(() => warrantColorIndexes.value.length + 2)
const colorIndexes = computed(() => Array.from({ length: Number(layoutForm.color_columns || 13) }, (_, index) => index + 1))
const selectedLayoutItem = computed(() => layoutForm.layout_items.find((item) => item.id === selectedLayoutItemId.value))
const layoutStyleLabel = computed(() => {
  const map: Record<string, string> = {
    three_section: '三段式版面',
    single_window: '整版窗口',
    text_only: '文字要求'
  }
  return map[layoutForm.diagram_style] || '三段式版面'
})
const entrustTitle = computed(() => {
  const orderType = String(layoutForm.title_mode || details.value.order_type || 'new_cylinder')
  const map: Record<string, string> = {
    new_cylinder: 'New Cylinder',
    old_cylinder: 'Revision / Remake',
    dechrome: 'Dechrome',
    rework: 'Rework',
    custom: String(layoutForm.custom_note || 'Plate Making')
  }
  return map[orderType] || 'Plate Making'
})
const unitText = computed(() => {
  const direct = value(detailRaw('unit'), '')
  if (direct) return direct
  const l = value(detailRaw('unit_l'), '')
  const w = value(detailRaw('unit_w'), '')
  return [l, w].filter(Boolean).join('*') || '-'
})
const horVerText = computed(() => value(detailRaw('hor_ver') || [detailRaw('straight'), detailRaw('crossway')].filter(Boolean).join('*')))
const widthText = computed(() => value(detailRaw('width') || detailRaw('unit_w') || engravingWidthLabel.value))
const lengthValue = computed(() => numeric(detailRaw('l_value')) || numeric(detailRaw('length')) || numeric(detailRaw('unit_w')))
const lengthValueLabel = computed(() => formatNumber(lengthValue.value) || value(detailRaw('l_value') || detailRaw('length') || detailRaw('unit_w'), ''))
const sampleNoText = computed(() => value(detailRaw('sample_no'), ''))
const primaryCylinderNoText = computed(() =>
  value(detailRaw('cylinder_id') || detailRaw('no') || detailRaw('sample_no') || sheet.value?.entrust_no || order.value.order_no)
)
const oldCylinderNoText = computed(() =>
  value(detailRaw('original_no') || detailRaw('old_cyl_no'), '')
)
const materialNewText = computed(() => value(detailRaw('material_new'), ''))
const diaText = computed(() => {
  const derivedDia = cComputed.value ? cComputed.value / Math.PI : 0
  return formatNumber(derivedDia) || value(detailRaw('dia') || firstColor.value.real_dia || firstColor.value.dia, '')
})
const returnsText = computed(() => value(detailRaw('returns') || returnsSummaryFromDetails(details.value)))
const orderDateText = computed(() => dateTimeText(detailRaw('order_datetime') || detailRaw('order_date') || order.value.order_date))
const listerText = computed(() => detailText('lister'))
const salesmanText = computed(() => detailText('salesman'))
const totalColorQty = computed(() => {
  const rows = inlineColorRows.value.length ? inlineColorRows.value : colorRows.value
  return rows.reduce((sum, row, index) => {
    if (!isActualColorRow(index)) return sum
    const qty = Number(row.qty || 0)
    return Number.isFinite(qty) ? sum + qty : sum
  }, 0) || value(detailRaw('total_qty'))
})
const markTestPositionText = computed(() => {
  const direct = value(detailRaw('mark_test_position'), '')
  if (direct) return direct
  return [
    detailRaw('mark_line') && `Mark: ${detailRaw('mark_line')}`,
    detailRaw('test_line') && `Test Line: ${detailRaw('test_line')}`,
    detailRaw('test_spot') && `Test Spot: ${detailRaw('test_spot')}`,
    detailRaw('computer_position') && `Computer: ${detailRaw('computer_position')}`,
    detailRaw('production_position') && `Production: ${detailRaw('production_position')}`
  ]
    .filter(Boolean)
    .join(' / ')
})
const unitLValue = computed(() => numeric(detailRaw('unit_l')) || numeric(detailRaw('l_value')) || 0)
const unitWValue = computed(() => numeric(detailRaw('unit_w')) || 0)
const straightInputValue = computed(() => numeric(detailRaw('straight')) || 0)
const centerRepeatCount = computed(() => clampInteger(straightInputValue.value || layoutForm.light_spot_horizontal, 1, 24, 1))
const straightValue = computed(() => centerRepeatCount.value)
const cComputed = computed(() => (unitLValue.value ? unitLValue.value * centerRepeatCount.value : numeric(detailRaw('c_value'))))
const unitLLabel = computed(() => formatNumber(unitLValue.value) || value(detailRaw('unit_l') || detailRaw('l_value'), 'Unit L'))
const unitWLabel = computed(() => formatNumber(unitWValue.value) || value(detailRaw('unit_w'), 'Unit W'))
const cValueLabel = computed(() => formatNumber(cComputed.value) || value(detailRaw('c_value'), 'C'))
const leftBroadenValue = computed(() => numeric(layoutForm.left_broaden) || 0)
const rightBroadenValue = computed(() => numeric(layoutForm.right_broaden) || numeric(layoutForm.right_label) || 0)
const middleBroadenValue = computed(() => numeric(layoutForm.middle_broaden) || 0)
const leftDetectionRawWidth = computed(() => Math.max(numeric(layoutForm.left_detection) || 0, 0))
const rightDetectionRawWidth = computed(() => Math.max(numeric(layoutForm.right_detection) || 0, 0))
const usesLeftMark = computed(() => Boolean(layoutForm.left_mark_enabled && (value(layoutForm.left_mark, '') || value(layoutForm.empty_move, ''))))
const usesRightMark = computed(() => Boolean(layoutForm.right_mark_enabled && (value(layoutForm.right_mark || layoutForm.right_move, '') || value(layoutForm.right_empty_move, ''))))
const usesLeftDetection = computed(() => Boolean(layoutForm.left_detection_enabled && (value(layoutForm.left_detection, '') || value(layoutForm.left_empty, ''))))
const usesRightDetection = computed(() => Boolean(layoutForm.right_detection_enabled && (value(layoutForm.right_detection, '') || value(layoutForm.right_empty, ''))))
const leftDetectionWidth = computed(() => (usesLeftDetection.value ? leftDetectionRawWidth.value : 0))
const rightDetectionWidth = computed(() => (usesRightDetection.value ? rightDetectionRawWidth.value : 0))
const leftEmptyValue = computed(() => Math.max(numeric(layoutForm.left_empty) || 0, 0))
const rightEmptyValue = computed(() => Math.max(numeric(layoutForm.right_empty) || 0, 0))
const gridColumnCount = computed(() => clampInteger(layoutForm.light_spot_horizontal, 1, 24, 1))
const gridRowCount = computed(() => clampInteger(layoutForm.light_spot_vertical, 1, 24, 1))
const gridLineWidth = computed(() => clampInteger(layoutForm.light_spot_width, 0, 12, 0))
const layoutTickMarks = computed(() => Array.from({ length: 11 }, (_, index) => index * 10))
const coreEngravingWidth = computed(() => leftBroadenValue.value + cComputed.value + middleBroadenValue.value + rightBroadenValue.value)
const repeatFormula = computed(() =>
  unitLValue.value ? `${formatNumber(unitLValue.value) || '0'}x${formatNumber(centerRepeatCount.value) || '1'}` : formatNumber(cComputed.value) || '0'
)
const engravingSegments = computed(() => {
  const segments = [
    usesLeftMark.value ? { label: 'Left Mark', value: numeric(layoutForm.left_mark) } : null,
    usesLeftMark.value ? { label: 'Empty Move', value: numeric(layoutForm.empty_move) } : null,
    usesLeftDetection.value ? { label: 'Left Detection', value: leftDetectionWidth.value } : null,
    { label: 'Left Empty', value: leftEmptyValue.value },
    { label: 'Left broaden', value: leftBroadenValue.value },
    { label: 'Unit L x Straight', value: cComputed.value, formula: repeatFormula.value },
    middleBroadenValue.value ? { label: 'Middle broaden', value: middleBroadenValue.value } : null,
    { label: 'Right broaden', value: rightBroadenValue.value },
    { label: 'Right Empty', value: rightEmptyValue.value },
    usesRightDetection.value ? { label: 'Right Detection', value: rightDetectionWidth.value } : null,
    usesRightMark.value ? { label: 'Right Empty Move', value: numeric(layoutForm.right_empty_move) } : null,
    usesRightMark.value ? { label: 'Right Mark', value: numeric(layoutForm.right_mark || layoutForm.right_move) } : null
  ]
  return segments.filter((segment): segment is { label: string; value: number; formula?: string } => Boolean(segment && Number.isFinite(segment.value)))
})
const engravingWidth = computed(() => engravingSegments.value.reduce((sum, segment) => sum + segment.value, 0))
const printingMarginValue = computed(() => numeric(layoutForm.printing_margin) || 0)
const printingWidth = computed(() => engravingWidth.value + printingMarginValue.value)
const coreEngravingWidthLabel = computed(() => formatFormulaNumber(coreEngravingWidth.value))
const engravingWidthLabel = computed(() => formatFormulaNumber(engravingWidth.value))
const printingMarginLabel = computed(() => formatNumber(printingMarginValue.value) || '0')
const printingWidthLabel = computed(() => formatFormulaNumber(printingWidth.value))
const coreEngravingFormula = computed(() => {
  const left = formatFormulaNumber(leftBroadenValue.value)
  const middle = middleBroadenValue.value ? `+${formatNumber(middleBroadenValue.value)}` : ''
  const right = formatFormulaNumber(rightBroadenValue.value)
  return `${left}+${repeatFormula.value}${middle}+${right}=${coreEngravingWidthLabel.value}`
})
const engravingFormula = computed(() => {
  const formula = engravingSegments.value.map((segment) => segment.formula || formatNumber(segment.value) || '0').join('+')
  return `${formula || '0'}=${engravingWidthLabel.value}`
})
const printingFormula = computed(() => `${engravingWidthLabel.value}+${printingMarginLabel.value}=${printingWidthLabel.value}`)
const sideLineScale = 14
const sideBoxPadding = 10
const fixedSideBoxWidth = 132
const fixedDetectionGap = 14
const leftEmptyOffset = computed(() => Math.max(numeric(layoutForm.empty_move) * sideLineScale, 0))
const rightEmptyOffset = computed(() => Math.max(numeric(layoutForm.right_empty_move) * sideLineScale, 0))
const leftDetectionGapPx = computed(() => {
  const rawGap = leftEmptyValue.value * sideLineScale
  return Math.min(Math.max(rawGap || fixedDetectionGap, fixedDetectionGap), fixedSideBoxWidth - 18)
})
const rightDetectionGapPx = computed(() => {
  const rawGap = rightEmptyValue.value * sideLineScale
  return Math.min(Math.max(rawGap || fixedDetectionGap, fixedDetectionGap), fixedSideBoxWidth - 18)
})
const canFillLeftSidePattern = computed(() => usesLeftDetection.value)
const canFillRightSidePattern = computed(() => usesRightDetection.value)
const leftSideBoxWidth = computed(() => fixedSideBoxWidth)
const rightSideBoxWidth = computed(() => fixedSideBoxWidth)
const layoutWindowStyle = computed(() => {
  return { gridTemplateColumns: `${leftSideBoxWidth.value}px minmax(0, 1fr) ${rightSideBoxWidth.value}px` }
})
const layoutWidthDimensionStyle = computed(() => ({
  left: `${leftSideBoxWidth.value}px`,
  right: `${rightSideBoxWidth.value}px`
}))
const layoutLeftBroadenLabelStyle = computed(() => ({
  left: `${leftSideBoxWidth.value}px`,
  right: 'auto'
}))
const layoutRightBroadenLabelStyle = computed(() => ({
  right: `${rightSideBoxWidth.value}px`,
  left: 'auto'
}))
function guidePairText(firstLabel: string, firstValue: unknown, secondLabel: string, secondValue: unknown) {
  return [
    value(firstValue, '') ? `${firstLabel}:${value(firstValue, '')}` : '',
    value(secondValue, '') ? `${secondLabel}:${value(secondValue, '')}` : ''
  ].filter(Boolean).join(' / ')
}

const printLayoutTopGuides = computed<LayoutTopGuide[]>(() => {
  const leftWidth = leftSideBoxWidth.value
  const rightWidth = rightSideBoxWidth.value
  const leftDetectionX = leftWidth - leftDetectionGapPx.value
  const rightDetectionX = rightDetectionGapPx.value
  const upper = '2px'
  const lower = '28px'
  const guide = (key: string, text: string, left: string, top = upper, className = ''): LayoutTopGuide | null => {
    if (!text.trim()) return null
    return { key, text, className, style: { left, top } }
  }
  return [
    usesLeftMark.value ? guide('lm-lem', guidePairText('LM', layoutForm.left_mark, 'LEM', layoutForm.empty_move), `${Math.max(Math.min(leftEmptyOffset.value || 56, leftWidth - 28), 38)}px`, upper, 'left-mark-guide') : null,
    usesLeftDetection.value ? guide('ld-le', guidePairText('LD', layoutForm.left_detection, 'LE', layoutForm.left_empty), `${Math.max(Math.min(leftDetectionX, leftWidth - 18), 34)}px`, lower, 'left-detection-guide') : null,
    guide('lc', value(layoutForm.left_color || layoutForm.layout_color, '') ? `LC:${value(layoutForm.left_color || layoutForm.layout_color, '')}` : '', `${leftWidth + 36}px`, upper, 'left-color-guide'),
    guide('mb', formatNumber(middleBroadenValue.value) ? `MB:${formatNumber(middleBroadenValue.value)}` : '', '50%', upper, 'middle-guide'),
    value(layoutForm.mid_mark_value, '') ? guide('mm', `MM:${value(layoutForm.mid_mark_value, '')}`, '50%', lower, 'middle-guide') : null,
    guide('rc', value(layoutForm.right_color || layoutForm.layout_color, '') ? `RC:${value(layoutForm.right_color || layoutForm.layout_color, '')}` : '', `calc(100% - ${rightWidth + 36}px)`, upper, 'right-color-guide'),
    usesRightDetection.value ? guide('rd-re', guidePairText('RD', layoutForm.right_detection, 'RE', layoutForm.right_empty), `calc(100% - ${Math.max(rightWidth - rightDetectionX, 34)}px)`, lower, 'right-detection-guide') : null,
    usesRightMark.value ? guide('rm-rem', guidePairText('RM', layoutForm.right_mark || layoutForm.right_move, 'REM', layoutForm.right_empty_move), `calc(100% - ${Math.max(Math.min(rightEmptyOffset.value || 56, rightWidth - 28), 38)}px)`, upper, 'right-mark-guide') : null
  ].filter((item): item is LayoutTopGuide => Boolean(item))
})
const layoutNearLineLabels = computed<LayoutLineLabel[]>(() => {
  const leftWidth = leftSideBoxWidth.value
  const rightWidth = rightSideBoxWidth.value
  const midMarkValue = value(layoutForm.mid_mark_value, '')
  const topMain = '-42px'
  const topMove = '-27px'
  const topDetect = '-12px'
  const leftMarkX = 8
  const leftDetectionX = leftWidth - leftDetectionGapPx.value
  const rightDetectionX = rightDetectionGapPx.value
  const rightEmptyMax = rightWidth - rightDetectionX - 14
  const rightEmptyX = Math.min(Math.max(rightEmptyOffset.value || Math.max((rightWidth - rightDetectionX) / 2, 34), 34), Math.max(rightEmptyMax, 34))
  const rightMarkX = 8
  const rightDetectionLabelX = rightWidth - rightDetectionX
  const rightEmptyLabelX = Math.min(Math.max(rightEmptyX, 54), rightWidth - 44)
  const labels: LayoutLineLabel[] = []
  const addLabel = (label: LayoutLineLabel, shouldShow = true) => {
    if (shouldShow && label.text.replace(/^[^:]+:/, '').trim()) labels.push(label)
  }
  if (usesLeftMark.value) {
    addLabel({
      key: 'lm',
      text: `LM:${value(layoutForm.left_mark, '')}`,
      className: 'align-left',
      style: { left: `${leftMarkX}px`, top: topMain }
    })
    addLabel({
      key: 'lem',
      text: `LEM:${value(layoutForm.empty_move, '')}`,
      className: 'align-left',
      style: { left: '24px', top: topMove }
    })
  }
  addLabel({
    key: 'lc',
    text: `LC:${value(layoutForm.left_color || layoutForm.layout_color, '')}`,
    className: 'align-left',
    style: { left: `${leftWidth + 12}px`, top: topMain }
  })
  addLabel({
    key: 'mb',
    text: `MB:${formatNumber(middleBroadenValue.value) || ''}${midMarkValue ? `  MM:${midMarkValue}` : ''}`,
    style: { left: '50%', top: topMain }
  }, Boolean(formatNumber(middleBroadenValue.value) || midMarkValue))
  addLabel({
    key: 'rc',
    text: `RC:${value(layoutForm.right_color || layoutForm.layout_color, '')}`,
    className: 'align-right',
    style: { right: `${rightWidth + 12}px`, top: topMain }
  })
  if (usesRightMark.value) {
    addLabel({
      key: 'rem',
      text: `REM:${value(layoutForm.right_empty_move, '')}`,
      style: { left: `calc(100% - ${rightEmptyLabelX}px)`, top: topMove }
    })
    addLabel({
      key: 'rm',
      text: `RM:${value(layoutForm.right_mark || layoutForm.right_move, '')}`,
      className: 'align-right',
      style: { right: `${rightMarkX}px`, top: topMain }
    })
  }
  if (usesLeftDetection.value) {
    addLabel({
      key: 'ld',
      text: `LD:${formatNumber(leftDetectionWidth.value) || ''} / LE:${formatNumber(leftEmptyValue.value) || ''}`,
      className: 'align-right',
      style: { left: `${leftDetectionX}px`, top: topDetect }
    })
  }
  if (usesRightDetection.value) {
    addLabel({
      key: 'rd',
      text: `RD:${formatNumber(rightDetectionWidth.value) || ''} / RE:${formatNumber(rightEmptyValue.value) || ''}`,
      style: { left: `calc(100% - ${rightDetectionLabelX}px)`, top: topDetect }
    })
  }
  return labels
})
const middleGridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${gridColumnCount.value}, minmax(0, 1fr))`,
  gridTemplateRows: `repeat(${gridRowCount.value}, minmax(0, 1fr))`,
  '--grid-line-width': `${gridLineWidth.value}px`
}))
const middleGridCells = computed(() =>
  Array.from({ length: gridColumnCount.value * gridRowCount.value }, (_, index) => ({
    index,
    lastCol: (index + 1) % gridColumnCount.value === 0,
    lastRow: index >= gridColumnCount.value * (gridRowCount.value - 1)
  }))
)
const lineItems = computed(() => {
  const items = layoutForm.layout_items.filter((item) => item.kind === 'line')
  const fullLineWidth = numeric(layoutForm.full_line_width)
  if (layoutForm.full_line && fullLineWidth > 0 && gridLineWidth.value > 0) {
    items.push({
      id: 'auto-full-line',
      kind: 'line',
      type: 'full_line',
      label: 'Full Line',
      symbol: '-',
      x: 0,
      y: 50,
      x2: 100,
      y2: 50,
      strokeWidth: fullLineWidth
    })
  }
  return items
})
const blockItems = computed(() => layoutForm.layout_items.filter((item) => item.kind === 'block'))
const markItems = computed(() => {
  const items = layoutForm.layout_items.filter((item) => item.kind === 'mark')
  const hasCenterPattern = layoutForm.layout_items.some((item) => item.groupId === 'auto-mid-pattern')
  if (layoutForm.mid_mark && !hasCenterPattern) {
    items.push({
      id: 'auto-mid-mark',
      kind: 'mark',
      type: 'left_flag_mark',
      label: 'Mid Mark',
      symbol: '',
      x: 50,
      y: 50,
      scaleX: 1,
      scaleY: 1.65
    })
  }
  if (layoutForm.left_self_mark) items.push({ id: 'auto-left-self-mark', kind: 'mark', type: 'self_mark', label: 'Left Self Mark', symbol: 'L', x: 8, y: 50 })
  return items
})
const lightSpotMarkers = computed(() => {
  const markers: string[] = []
  if (layoutForm.light_spot_upper_left) markers.push('upper-left')
  if (layoutForm.light_spot_upper_right) markers.push('upper-right')
  if (layoutForm.light_spot_lower_left) markers.push('lower-left')
  if (layoutForm.light_spot_lower_right) markers.push('lower-right')
  return markers
})
const leftDetectionLineStyle = computed(() => ({
  right: `${leftDetectionGapPx.value}px`
}))
const rightDetectionLineStyle = computed(() => ({
  left: `${rightDetectionGapPx.value}px`
}))
const detectionLabel = computed(() => `${formatNumber(leftDetectionWidth.value) || '0'} / ${formatNumber(rightDetectionWidth.value) || '0'}`)

function value(input: unknown, fallback = '-') {
  const text = input === null || input === undefined ? '' : String(input)
  return text.trim() || fallback
}

function dateTimeText(input: unknown, fallback = '-') {
  const text = value(input, '')
  if (!text) return fallback
  return text.replace('T', ' ').replace(/\.\d+Z?$/, '').slice(0, 19)
}

function textValue(input: unknown) {
  return input === null || input === undefined ? '' : String(input)
}

function returnsSummaryFromDetails(sourceDetails: Record<string, unknown>) {
  const rows = [
    ['returns_color_print', 'Color Print'],
    ['returns_laser_print', 'Laser Print'],
    ['returns_sample', 'Sample'],
    ['returns_chromalin_print', 'Chromalin Print'],
    ['returns_color_separation', 'Color Separation'],
    ['returns_proofing_color_print', 'Proofing color Print']
  ]
  return rows
    .map(([key, label]) => {
      const quantity = textValue(sourceDetails[key]).trim()
      return quantity && quantity !== '0' ? `${label}: ${quantity}` : ''
    })
    .filter(Boolean)
    .join(' / ')
}

function detailRaw(key: string, fallback?: unknown) {
  return Object.prototype.hasOwnProperty.call(inlineDetails, key) ? inlineDetails[key] : fallback ?? details.value[key]
}

function detailText(key: string, fallback?: unknown) {
  return value(detailRaw(key, fallback))
}

function setInlineDetail(key: string, input: unknown) {
  inlineDetails[key] = textValue(input)
  syncInlineDerivedFields(key)
  syncLayoutNcFromInline(key)
}

function formatDerivedNumber(input: number) {
  if (!Number.isFinite(input) || input <= 0) return ''
  return input.toFixed(3).replace(/\.?0+$/, '')
}

function syncInlineDia() {
  const cir = numeric(inlineDetails.c_value)
  if (cir) {
    inlineDetails.dia = formatDerivedNumber(cir / Math.PI)
  }
}

function syncInlineDerivedFields(changedKey: string) {
  const unitL = numeric(inlineDetails.unit_l)
  const cir = numeric(inlineDetails.c_value)
  const nc = numeric(inlineDetails.straight)
  if (unitL && cir && (!nc || changedKey === 'c_value')) {
    inlineDetails.straight = formatDerivedNumber(cir / unitL)
    syncInlineDia()
    syncLayoutNcFromInline('straight')
    return
  }
  if (unitL && nc && (changedKey === 'unit_l' || changedKey === 'straight' || !cir)) {
    inlineDetails.c_value = formatDerivedNumber(unitL * nc)
  }
  syncInlineDia()
  syncLayoutNcFromInline(changedKey)
}

function syncLayoutNcFromInline(key: string) {
  if (key === 'straight') {
    const value = numeric(inlineDetails.straight)
    if (value > 0) layoutForm.light_spot_horizontal = clampInteger(value, 1, 24, 1)
  }
  if (key === 'crossway') {
    const value = numeric(inlineDetails.crossway)
    if (value > 0) layoutForm.light_spot_vertical = clampInteger(value, 1, 24, 1)
  }
}

function ensureInlineColorRows() {
  while (inlineColorRows.value.length < maxInlineColorRows) {
    const index = inlineColorRows.value.length
    inlineColorRows.value.push({ color_no: defaultColorNo(index) })
  }
}

function setInlineColorValue(rowIndex: number, key: string, input: unknown) {
  ensureInlineColorRows()
  if (!isActualColorRow(rowIndex) && ['qty', 'printing_method', 'real_dia', 'dia'].includes(key)) {
    inlineColorRows.value[rowIndex][key] = ''
    return
  }
  inlineColorRows.value[rowIndex][key] = textValue(input)
  if (key === 'qty' && !textValue(input).trim()) {
    inlineColorRows.value[rowIndex].printing_method = ''
  }
}

function inlineColorRaw(rowIndex: number, key: string, fallback?: unknown) {
  ensureInlineColorRows()
  const row = inlineColorRows.value[rowIndex]
  if (!isActualColorRow(rowIndex) && ['qty', 'printing_method', 'real_dia', 'dia'].includes(key)) {
    row[key] = ''
    return ''
  }
  if (!Object.prototype.hasOwnProperty.call(row, key)) {
    row[key] = textValue(fallback ?? colorRows.value[rowIndex]?.[key])
  }
  return row[key]
}

function inlineColorText(rowIndex: number, key: string, fallback?: unknown) {
  return value(inlineColorRaw(rowIndex, key, fallback), '')
}

function colorQtyRaw(rowIndex: number) {
  ensureInlineColorRows()
  if (!isActualColorRow(rowIndex)) return ''
  return textValue(inlineColorRows.value[rowIndex]?.qty || colorRows.value[rowIndex]?.qty || (isFirstActualColorRow(rowIndex) ? detailRaw('total_qty') : ''))
}

function colorQtyFallback(rowIndex: number) {
  if (!isActualColorRow(rowIndex)) return ''
  return textValue(colorRows.value[rowIndex]?.qty || (isFirstActualColorRow(rowIndex) ? detailRaw('total_qty') : ''))
}

function colorDiaFallback(rowIndex: number) {
  if (!isActualColorRow(rowIndex)) return ''
  return textValue(colorRows.value[rowIndex]?.real_dia || colorRows.value[rowIndex]?.dia || (isFirstActualColorRow(rowIndex) ? diaText.value : ''))
}

function printMethodFallback(rowIndex: number) {
  if (!isActualColorRow(rowIndex)) return ''
  if (!colorQtyRaw(rowIndex).trim()) return ''
  return textValue(inlineColorRows.value[rowIndex]?.printing_method || colorRows.value[rowIndex]?.printing_method || detailRaw('printing_method'))
}

function hydrateInlineContent(source: SalesOrder) {
  const sourceDetails = source.plate_details || {}
  editableDetailKeys.forEach((key) => {
    inlineDetails[key] = textValue(sourceDetails[key])
  })
  inlineDetails.product_name ||= textValue(source.product_summary)
  inlineDetails.cylinder_id ||= textValue(sourceDetails.cylinder_id || sourceDetails.no || sourceDetails.sample_no || source.order_no)
  inlineDetails.no ||= textValue(sourceDetails.no || sourceDetails.cylinder_id || sourceDetails.sample_no || source.order_no)
  inlineDetails.sample_no ||= textValue(sourceDetails.sample_no)
  inlineDetails.original_no ||= textValue(sourceDetails.original_no || sourceDetails.old_cyl_no)
  inlineDetails.old_cyl_no ||= textValue(sourceDetails.old_cyl_no || sourceDetails.original_no)
  inlineDetails.material_model ||= textValue(sourceDetails.material_model || sourceDetails.cylinder_model)
  inlineDetails.material_new ||= textValue(sourceDetails.material_new)
  inlineDetails.unit ||= [sourceDetails.unit_l, sourceDetails.unit_w].map(textValue).filter(Boolean).join('*')
  inlineDetails.hor_ver ||= [sourceDetails.straight, sourceDetails.crossway].map(textValue).filter(Boolean).join('*')
  inlineDetails.width ||= textValue(sourceDetails.width || sourceDetails.unit_w)
  inlineDetails.l_value ||= textValue(sourceDetails.l_value || sourceDetails.unit_l)
  inlineDetails.returns ||= textValue(sourceDetails.returns || returnsSummaryFromDetails(sourceDetails))
  inlineDetails.order_datetime ||= textValue(sourceDetails.order_datetime || sourceDetails.order_date || source.order_date)
  syncInlineDerivedFields('hydrate')
  syncLayoutNcFromInline('straight')
  syncLayoutNcFromInline('crossway')

  inlineColorRows.value = Array.from({ length: maxInlineColorRows }, (_, index) => ({ color_no: defaultColorNo(index) }))
  ;(source.color_rows || []).forEach((row, index) => {
    if (index >= maxInlineColorRows) return
    editableColorKeys.forEach((key) => {
      inlineColorRows.value[index][key] = textValue(row[key])
    })
    inlineColorRows.value[index].color_no = defaultColorNo(index)
  })
  ensureInlineColorRows()
  inlineColorRows.value.forEach((row, index) => {
    row.color_no = defaultColorNo(index)
    if (!isActualColorRow(index)) {
      row.qty = ''
      row.dia = ''
      row.real_dia = ''
      row.printing_method = ''
      return
    }
    if (isFirstActualColorRow(index)) {
      row.qty ||= textValue(sourceDetails.total_qty)
      row.dia ||= diaText.value
      row.real_dia ||= row.dia
    }
    if (textValue(row.qty).trim() && !row.printing_method) {
      row.printing_method = textValue(sourceDetails.printing_method)
    }
  })
}

function inlineDetailsPayload() {
  const payload = Object.fromEntries(editableDetailKeys.map((key) => [key, inlineDetails[key] ?? '']))
  payload.cylinder_id ||= payload.no || payload.sample_no || ''
  payload.no ||= payload.cylinder_id || payload.sample_no || ''
  payload.sample_no ||= ''
  payload.original_no ||= payload.old_cyl_no || ''
  payload.unit ||= [payload.unit_l, payload.unit_w].filter(Boolean).join('*')
  payload.hor_ver ||= [payload.straight, payload.crossway].filter(Boolean).join('*')
  payload.width ||= payload.unit_w || ''
  payload.l_value ||= payload.unit_l || ''
  payload.dia = diaText.value
  payload.material_new ||= ''
  return payload
}

function inlineColorRowsPayload() {
  ensureInlineColorRows()
  return inlineColorRows.value.slice(0, Number(layoutForm.color_columns || 13)).map((row, index) => {
    const isActualRow = isActualColorRow(index)
    const qty = isActualRow ? row.qty || (isFirstActualColorRow(index) ? inlineDetails.total_qty || '' : '') : ''
    const dia = isActualRow ? row.dia || row.real_dia || (isFirstActualColorRow(index) ? diaText.value : '') : ''
    const realDia = isActualRow ? row.real_dia || row.dia || (isFirstActualColorRow(index) ? diaText.value : '') : ''
    return {
      color_no: defaultColorNo(index),
      print_color: row.print_color || '',
      qty,
      real_dia: realDia,
      dia,
      public_no: row.public_no || '',
      printing_method: isActualRow && textValue(qty).trim() ? row.printing_method || inlineDetails.printing_method || '' : '',
      remarks: row.remarks || ''
    }
  })
}

const InlineCell = defineComponent({
  name: 'InlineCell',
  props: {
    field: { type: String, required: true },
    fallback: { type: [String, Number, Boolean] as PropType<PlateValue>, default: '' },
    multiline: { type: Boolean, default: false }
  },
  setup(props) {
    return () => {
      if (!Object.prototype.hasOwnProperty.call(inlineDetails, props.field)) {
        setInlineDetail(props.field, props.fallback)
      }
      const displayText = detailText(props.field, props.fallback)
      const tag = props.multiline ? 'textarea' : 'input'
      const editor = canUpdateLayout.value
        ? h(tag, {
            class: props.multiline ? 'cell-textarea no-print' : 'cell-input no-print',
            value: inlineDetails[props.field] ?? '',
            list: props.field === 'printing_method' ? 'printing-method-options' : undefined,
            onInput: (event: Event) => setInlineDetail(props.field, (event.target as HTMLInputElement).value)
          })
        : h('span', displayText)
      return [h('span', { class: 'print-only' }, displayText), editor]
    }
  }
})

const InlineColorCell = defineComponent({
  name: 'InlineColorCell',
  props: {
    rowIndex: { type: Number, required: true },
    field: { type: String, required: true },
    fallback: { type: [String, Number, Boolean] as PropType<PlateValue>, default: '' }
  },
  setup(props) {
    return () => {
      const displayText = inlineColorText(props.rowIndex, props.field, props.fallback)
      const editor = canUpdateLayout.value
        ? h('input', {
            class: 'cell-input cell-input-compact no-print',
            value: inlineColorRows.value[props.rowIndex]?.[props.field] ?? '',
            list: props.field === 'printing_method' ? 'printing-method-options' : undefined,
            onInput: (event: Event) => setInlineColorValue(props.rowIndex, props.field, (event.target as HTMLInputElement).value)
          })
        : h('span', displayText)
      return [h('span', { class: 'print-only' }, displayText), editor]
    }
  }
})

function scrollToLayoutEditor() {
  layoutEditorRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function numeric(input: unknown) {
  const normalized = String(input ?? '').replace(/,/g, '').trim()
  if (!normalized) return 0
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatNumber(input: number) {
  if (!Number.isFinite(input) || input === 0) return ''
  return input.toFixed(2).replace(/\.?0+$/, '')
}

function formatFormulaNumber(input: number) {
  return formatNumber(input) || '0'
}

function defaultColorNo(rowIndex: number) {
  return String(rowIndex - 2)
}

function colorNoNumber(rowIndex: number) {
  const parsed = Number(defaultColorNo(rowIndex))
  return Number.isFinite(parsed) ? parsed : 0
}

function isActualColorRow(rowIndex: number) {
  return colorNoNumber(rowIndex) >= 1
}

function isFirstActualColorRow(rowIndex: number) {
  return colorNoNumber(rowIndex) === 1
}

function clampInteger(input: unknown, min: number, max: number, fallback: number) {
  const parsed = Math.round(numeric(input))
  if (!Number.isFinite(parsed) || parsed < min) return fallback
  return Math.min(parsed, max)
}

function scaleValue(input?: number) {
  const parsed = Number(input ?? 1)
  if (!Number.isFinite(parsed)) return 1
  return Math.max(0.1, Math.min(parsed, 8))
}

function axisScaleValue(input?: number, max = 12) {
  const parsed = Number(input ?? 1)
  if (!Number.isFinite(parsed)) return 1
  return Math.max(0.1, Math.min(parsed, max))
}

function isFlagItem(item?: Pick<LayoutItem, 'type'> | null) {
  return item?.type === 'left_flag_mark' || item?.type === 'right_flag_mark'
}

function isSidePatternStack(item?: Pick<LayoutItem, 'type'> | null) {
  return item?.type === 'side_pattern_mark_stack' || item?.type === 'side_pattern_mark_stack_right'
}

function isScalableMark(item?: Pick<LayoutItem, 'type'> | null) {
  return isFlagItem(item) || isSidePatternStack(item)
}

function itemScaleX(item: LayoutItem) {
  return scaleValue(item.scale) * (isScalableMark(item) ? axisScaleValue(item.scaleX, 12) : 1)
}

function itemScaleY(item: LayoutItem) {
  return scaleValue(item.scale) * (isScalableMark(item) ? axisScaleValue(item.scaleY, 12) : 1)
}

function rotationValue(input?: number) {
  const parsed = Number(input ?? 0)
  if (!Number.isFinite(parsed)) return 0
  return Math.max(-180, Math.min(parsed, 180))
}

function addLayoutItem(tool: LayoutTool) {
  if (tool.type === 'select') {
    activeTool.value = 'select'
    selectedLayoutItemId.value = ''
    focusLayoutCanvas()
    return
  }
  const created = createLayoutItems(tool)
  layoutForm.layout_items.push(...created)
  selectedLayoutItemId.value = created[created.length - 1]?.id || ''
  activeTool.value = 'select'
  focusLayoutCanvas()
}

function createLayoutItems(tool: LayoutTool, point?: { x: number; y: number }): LayoutItem[] {
  const offset = layoutForm.layout_items.length % 6
  const baseId = `${Date.now()}-${layoutForm.layout_items.length}`
  const x = point ? point.x : Math.min(tool.defaultX + offset * 2, 88)
  const y = point ? point.y : Math.min(tool.defaultY + offset * 2, 88)
  const atX = (value?: number) => clampPercent(point ? x + (Number(value ?? tool.defaultX) - 50) : Math.min((value || 0) + offset * 2, 96))
  const atY = (value?: number) => clampPercent(point ? y + (Number(value ?? tool.defaultY) - 50) : Math.min((value || 0) + offset * 2, 96))
  const line = (suffix: string, x1: number, y1: number, x2: number, y2: number): LayoutItem => ({
    id: `${baseId}-${suffix}`,
    kind: 'line',
    type: tool.type,
    label: tool.label,
    symbol: tool.symbol,
    x: x1,
    y: y1,
    x2,
    y2,
    strokeWidth: tool.strokeWidth || 2,
    dashed: Boolean(tool.dashed),
    arrow: Boolean(tool.arrow),
    arrowStart: Boolean(tool.arrowStart),
    rotation: 0,
    scale: 1,
    groupId: tool.group ? baseId : undefined
  })
  if (tool.group === 'cross') {
    const crossHalf = point ? 4 : 8
    return [
      line('h', clampPercent(x - crossHalf), y, clampPercent(x + crossHalf), y),
      line('v', x, clampPercent(y - crossHalf), x, clampPercent(y + crossHalf))
    ]
  }
  if (tool.group === 'parallel') {
    return [-6, 0, 6].map((delta, index) => line(String(index), clampPercent(x - 18), clampPercent(y + delta), clampPercent(x + 18), clampPercent(y + delta)))
  }
  if (tool.group === 'cornerLeft') {
    return [
      line('v', x, clampPercent(y - 18), x, clampPercent(y + 18)),
      line('h', clampPercent(x - 18), y, clampPercent(x + 8), y)
    ]
  }
  if (tool.group === 'cornerBottom') {
    return [
      line('h', clampPercent(x - 18), y, clampPercent(x + 18), y),
      line('v', x, clampPercent(y - 18), x, clampPercent(y + 8))
    ]
  }
  if (tool.group === 'teeLine') {
    return [
      line('v', x, clampPercent(y - 18), x, clampPercent(y + 18)),
      line('h', x, y, clampPercent(x + 18), y)
    ]
  }
  if (tool.kind === 'line') {
    return [line('line', atX(tool.defaultX), atY(tool.defaultY), atX(tool.defaultX2 || tool.defaultX), atY(tool.defaultY2 || tool.defaultY))]
  }
  if (tool.kind === 'block') {
    const width = tool.width || 5
    const height = tool.height || 5
    return [{
      id: `${baseId}-block`,
      kind: 'block',
      type: tool.type,
      label: tool.label,
      symbol: tool.symbol,
      x: clampPercent(x - width / 2),
      y: clampPercent(y - height / 2),
      width,
      height,
      rotation: 0,
      scale: 1
    }]
  }
  return [{
    id: `${baseId}-mark`,
    kind: 'mark',
    type: tool.type,
    label: tool.label,
    symbol: tool.symbol,
    x,
    y,
    rotation: 0,
    scale: 1,
    scaleX: tool.type.includes('flag_mark') ? 1 : undefined,
    scaleY: tool.type.includes('flag_mark') ? 1.25 : undefined
  }]
}

function fillSidePatternWithChoice(side: 'left' | 'right') {
  const canFill = side === 'left' ? canFillLeftSidePattern.value : canFillRightSidePattern.value
  if (!canFill) {
    ElMessage.warning(side === 'left' ? 'Left Mark and Left Detection are required' : 'Right Mark and Right Detection are required')
    return
  }
  const input = window.prompt('Keep upper guide pattern? Enter 1 = keep, 0 = remove', '1')
  if (input === null) return
  const normalized = input.trim().toLowerCase()
  if (!['1', '0', 'yes', 'no', 'y', 'n', 'true', 'false'].includes(normalized)) {
    ElMessage.warning('Please enter 1 or 0')
    return
  }
  fillSidePattern(side, ['1', 'yes', 'y', 'true'].includes(normalized))
}

function fillSidePattern(side: 'left' | 'right', keepTopLine: boolean) {
  const bounds = sidePatternBounds(side)
  if (!bounds || bounds.width < 1.5) {
    ElMessage.warning('Pattern area is too narrow')
    return
  }
  const groupId = `auto-side-pattern-${side}`
  layoutForm.layout_items = layoutForm.layout_items.filter((item) => item.groupId !== groupId)
  const idBase = `${groupId}-${Date.now()}`
  const items = createSidePatternItems(side, bounds, keepTopLine, idBase, groupId)
  layoutForm.layout_items.push(...items)
  selectedLayoutItemId.value = items[0]?.id || ''
  activeTool.value = 'select'
  ElMessage.success(side === 'left' ? 'Left side pattern filled' : 'Right side pattern filled')
}

function sidePatternText(kind: '1mm' | '20mm') {
  return value(kind === '1mm' ? layoutForm.pattern_1mm_label : layoutForm.pattern_20mm_label, '')
}

function syncSidePatternTextLabels() {
  layoutForm.layout_items.forEach((item) => {
    const groupId = String(item.groupId || '')
    if (item.kind !== 'mark' || item.type !== 'side_pattern_text' || (!groupId.startsWith('auto-side-pattern') && groupId !== 'auto-mid-pattern')) return
    if (item.id.includes('-text-1mm')) item.symbol = sidePatternText('1mm')
    if (item.id.includes('-text-20mm')) item.symbol = sidePatternText('20mm')
  })
}

function fillMidMarkPatternWithChoice() {
  const input = window.prompt('Keep upper guide pattern? Enter 1 = keep, 0 = remove', '1')
  if (input === null) return
  const normalized = input.trim().toLowerCase()
  if (!['1', '0', 'yes', 'no', 'y', 'n', 'true', 'false'].includes(normalized)) {
    ElMessage.warning('Please enter 1 or 0')
    return
  }
  fillMidMarkPattern(['1', 'yes', 'y', 'true'].includes(normalized))
}

function fillMidMarkPattern(keepTopLine: boolean) {
  const groupId = 'auto-mid-pattern'
  layoutForm.layout_items = layoutForm.layout_items.filter((item) => item.groupId !== groupId)
  const idBase = `${groupId}-${Date.now()}`
  const items = createMidPatternItems(keepTopLine, idBase, groupId)
  layoutForm.layout_items.push(...items)
  layoutForm.mid_mark = false
  selectedLayoutItemId.value = items[0]?.id || ''
  activeTool.value = 'select'
  ElMessage.success('Middle mark pattern filled')
}

function sidePatternBounds(side: 'left' | 'right') {
  const totalWidth = Math.max(layoutCanvasRef.value?.clientWidth || 0, leftSideBoxWidth.value + rightSideBoxWidth.value + 720)
  if (side === 'left') {
    const detectionPx = leftSideBoxWidth.value - leftDetectionGapPx.value
    const start = 0
    const end = (detectionPx / totalWidth) * 100
    return { start, end, width: end - start }
  }
  const rightStartPx = totalWidth - rightSideBoxWidth.value
  const detectionPx = rightStartPx + rightDetectionGapPx.value
  const start = (detectionPx / totalWidth) * 100
  const end = 100
  return { start, end, width: end - start }
}

function createSidePatternItems(
  side: 'left' | 'right',
  bounds: { start: number; end: number; width: number },
  keepTopLine: boolean,
  idBase: string,
  groupId: string,
  labelOverride = ''
) {
  const items: LayoutItem[] = []
  const itemLabel = labelOverride || (side === 'left' ? 'Left side pattern' : 'Right side pattern')
  const margin = Math.min(Math.max(bounds.width * 0.1, 0.35), 0.75)
  const patternStart = bounds.start + margin
  const patternEnd = bounds.end - margin
  const width = Math.max(patternEnd - patternStart, 1.8)
  const localX = (unit: number) => side === 'left'
    ? patternStart + width * unit
    : patternEnd - width * unit
  const spanX = (from: number, to: number) => {
    const x1 = localX(from)
    const x2 = localX(to)
    return { x: Math.min(x1, x2), width: Math.max(Math.abs(x2 - x1), 0.6) }
  }
  const line = (suffix: string, x1: number, y1: number, x2: number, y2: number, dashed = false): LayoutItem => ({
    id: `${idBase}-${suffix}`,
    kind: 'line',
    type: dashed ? 'side_pattern_dashed_line' : 'side_pattern_line',
    label: itemLabel,
    symbol: '-',
    x: clampPercent(x1),
    y: clampPercent(y1),
    x2: clampPercent(x2),
    y2: clampPercent(y2),
    strokeWidth: dashed ? 1.6 : 2,
    dashed,
    rotation: 0,
    scale: 1,
    groupId
  })
  const block = (suffix: string, from: number, to: number, y: number, height = 2.5): LayoutItem => {
    const span = spanX(from, to)
    return {
      id: `${idBase}-${suffix}`,
      kind: 'block',
      type: 'side_pattern_block',
      label: itemLabel,
      symbol: '[]',
      x: clampPercent(span.x),
      y: clampPercent(y),
      width: Math.min(span.width, 100 - span.x),
      height,
      rotation: 0,
      scale: 1,
      groupId
    }
  }
  const mark = (suffix: string, type: string, symbol: string, unitX: number, y: number, scaleX = 1, scaleY = 1): LayoutItem => ({
    id: `${idBase}-${suffix}`,
    kind: 'mark',
    type,
    label: itemLabel,
    symbol,
    x: clampPercent(localX(unitX)),
    y: clampPercent(y),
    rotation: 0,
    scale: 1,
    scaleX,
    scaleY,
    groupId
  })

  const labelX = 0.22
  const labelLineStart = 0.04
  const labelLineEnd = 0.50
  const barStart = 0.56
  const barEnd = 0.92
  const guideLeft = 0.53
  const guideRight = 0.94
  const stackCenter = (barStart + barEnd) / 2

  items.push(line('pattern-guide-left', localX(guideLeft), 0, localX(guideLeft), 100, true))
  items.push(line('pattern-guide-right', localX(guideRight), 0, localX(guideRight), 100, true))
  if (keepTopLine) {
    items.push(line('top-reference', localX(labelLineStart), 7.5, localX(barEnd), 7.5))
    items.push(line('guide-1mm', localX(labelLineStart), 14, localX(labelLineEnd), 14))
    items.push(line('guide-20mm', localX(labelLineStart), 21, localX(labelLineEnd), 21))
    items.push(mark('text-1mm', 'side_pattern_text', sidePatternText('1mm'), labelX, 12.1, 0.66, 0.66))
    items.push(block('bar-1mm', barStart, barEnd, 14.7, 2))
    items.push(mark('text-20mm', 'side_pattern_text', sidePatternText('20mm'), labelX, 18.8, 0.66, 0.66))
    ;[20.8, 26.1, 31.4, 36.7, 42, 47.3].forEach((y, index) => {
      items.push(block(`bar-20mm-${index}`, barStart, barEnd, y, 2))
    })
  }

  items.push(mark(
    'mark-stack',
    side === 'left' ? 'side_pattern_mark_stack' : 'side_pattern_mark_stack_right',
    side,
    stackCenter,
    70,
    1,
    1.05
  ))

  return items
}

function createMidPatternItems(keepTopLine: boolean, idBase: string, groupId: string) {
  return createSidePatternItems(
    'left',
    { start: 43, end: 57, width: 14 },
    keepTopLine,
    idBase,
    groupId,
    'Middle mark pattern'
  )
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
}

function layoutPoint(event: PointerEvent) {
  const rect = layoutCanvasRef.value?.getBoundingClientRect()
  if (!rect || !rect.width || !rect.height) return { x: 50, y: 50 }
  return {
    x: clampPercent(((event.clientX - rect.left) / rect.width) * 100),
    y: clampPercent(((event.clientY - rect.top) / rect.height) * 100)
  }
}

function handleLayoutCanvasPointerDown(event: PointerEvent) {
  const point = layoutPoint(event)
  const hitItem = findLayoutItemAtPoint(point)
  if (hitItem) {
    beginLayoutDrag(event, hitItem, point)
    return
  }
  const tool = layoutTools.find((entry) => entry.type === activeTool.value)
  if (!tool || tool.type === 'select') {
    selectedLayoutItemId.value = ''
    return
  }
  const created = createLayoutItems(tool, point)
  layoutForm.layout_items.push(...created)
  selectedLayoutItemId.value = created[created.length - 1]?.id || ''
  if (tool.type === 'solid_block' || tool.group === 'cross') {
    beginLayoutToolDraw(event, created[0], point, tool.group === 'cross' ? 'draw-cross' : 'draw-block')
  } else {
    activeTool.value = 'select'
  }
  focusLayoutCanvas()
}

function beginLayoutToolDraw(event: PointerEvent, item: LayoutItem, point: { x: number; y: number }, mode: 'draw-block' | 'draw-cross') {
  selectedLayoutItemId.value = item.id
  draggingLayoutItem.value = {
    id: item.id,
    mode,
    lastX: point.x,
    lastY: point.y,
    startX: point.x,
    startY: point.y,
    centerX: point.x,
    centerY: point.y,
    startScale: 1,
    startScaleX: 1,
    startScaleY: 1,
    startRotation: 0
  }
  layoutCanvasRef.value?.setPointerCapture(event.pointerId)
  window.removeEventListener('pointermove', handleLayoutPointerMove)
  window.removeEventListener('pointerup', handleLayoutPointerUp)
  window.addEventListener('pointermove', handleLayoutPointerMove)
  window.addEventListener('pointerup', handleLayoutPointerUp)
}

function startLayoutDrag(event: PointerEvent, item: LayoutItem) {
  if (String(item.id).startsWith('auto-')) return
  const savedItem = layoutForm.layout_items.find((entry) => entry.id === item.id)
  if (!savedItem) return
  const point = layoutPoint(event)
  beginLayoutDrag(event, savedItem, point)
}

function beginLayoutDrag(event: PointerEvent, savedItem: LayoutItem, point: { x: number; y: number }) {
  activeTool.value = 'select'
  selectedLayoutItemId.value = savedItem.id
  const center = itemCenter(savedItem)
  draggingLayoutItem.value = {
    id: savedItem.id,
    mode: 'move',
    lastX: point.x,
    lastY: point.y,
    startX: point.x,
    startY: point.y,
    centerX: center.x,
    centerY: center.y,
    startScale: scaleValue(savedItem.scale),
    startScaleX: axisScaleValue(savedItem.scaleX, 12),
    startScaleY: axisScaleValue(savedItem.scaleY, 12),
    startRotation: rotationValue(savedItem.rotation)
  }
  layoutCanvasRef.value?.setPointerCapture(event.pointerId)
  window.removeEventListener('pointermove', handleLayoutPointerMove)
  window.removeEventListener('pointerup', handleLayoutPointerUp)
  window.addEventListener('pointermove', handleLayoutPointerMove)
  window.addEventListener('pointerup', handleLayoutPointerUp)
  focusLayoutCanvas()
}

function startLayoutTransform(event: PointerEvent, mode: 'resize' | 'rotate') {
  const item = selectedLayoutItem.value
  if (!item || String(item.id).startsWith('auto-')) return
  const point = layoutPoint(event)
  const center = itemCenter(item)
  activeTool.value = 'select'
  draggingLayoutItem.value = {
    id: item.id,
    mode,
    lastX: point.x,
    lastY: point.y,
    startX: point.x,
    startY: point.y,
    centerX: center.x,
    centerY: center.y,
    startScale: scaleValue(item.scale),
    startScaleX: axisScaleValue(item.scaleX, 12),
    startScaleY: axisScaleValue(item.scaleY, 12),
    startRotation: rotationValue(item.rotation),
    startItems: mode === 'rotate' ? layoutItemGroup(item).map(layoutItemSnapshot) : undefined
  }
  layoutCanvasRef.value?.setPointerCapture(event.pointerId)
  window.removeEventListener('pointermove', handleLayoutPointerMove)
  window.removeEventListener('pointerup', handleLayoutPointerUp)
  window.addEventListener('pointermove', handleLayoutPointerMove)
  window.addEventListener('pointerup', handleLayoutPointerUp)
  focusLayoutCanvas()
}

function startLayoutEndpointDrag(event: PointerEvent, endpoint: 'start' | 'end') {
  const item = selectedLayoutItem.value
  if (!item || item.kind !== 'line' || String(item.id).startsWith('auto-')) return
  const point = layoutPoint(event)
  const center = itemCenter(item)
  activeTool.value = 'select'
  draggingLayoutItem.value = {
    id: item.id,
    mode: endpoint === 'start' ? 'line-start' : 'line-end',
    lastX: point.x,
    lastY: point.y,
    startX: point.x,
    startY: point.y,
    centerX: center.x,
    centerY: center.y,
    startScale: scaleValue(item.scale),
    startScaleX: axisScaleValue(item.scaleX, 12),
    startScaleY: axisScaleValue(item.scaleY, 12),
    startRotation: rotationValue(item.rotation)
  }
  layoutCanvasRef.value?.setPointerCapture(event.pointerId)
  window.removeEventListener('pointermove', handleLayoutPointerMove)
  window.removeEventListener('pointerup', handleLayoutPointerUp)
  window.addEventListener('pointermove', handleLayoutPointerMove)
  window.addEventListener('pointerup', handleLayoutPointerUp)
  focusLayoutCanvas()
}

function focusLayoutCanvas() {
  nextTick(() => layoutCanvasRef.value?.focus())
}

function handleLayoutCanvasKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && ['INPUT', 'TEXTAREA'].includes(target.tagName)) return
  const item = selectedLayoutItem.value
  if (!item) return
  if (event.key === 'Delete') {
    removeLayoutItem(item.id)
    event.preventDefault()
    return
  }
  if (item.kind !== 'mark') return
  if (event.key === 'Backspace') {
    item.symbol = item.symbol.slice(0, -1) || 'T'
    event.preventDefault()
    return
  }
  if (event.key.length === 1) {
    item.symbol = item.type === 'text' && item.symbol === 'T' ? event.key : `${item.symbol}${event.key}`
    event.preventDefault()
  }
}

function findLayoutItemAtPoint(point: { x: number; y: number }) {
  const items = [...layoutForm.layout_items].reverse()
  return items.find((item) => {
    if (item.kind === 'line') {
      return lineDistance(point, item) <= 10
    }
    if (item.kind === 'block') {
      return point.x >= item.x - 4 && point.x <= item.x + (item.width || 5) + 4 && point.y >= item.y - 4 && point.y <= item.y + (item.height || 5) + 4
    }
    if (isScalableMark(item)) {
      const bounds = itemBounds(item)
      const center = itemCenter(item)
      const width = Math.max(bounds.width * itemScaleX(item), 8)
      const height = Math.max(bounds.height * itemScaleY(item), 12)
      return point.x >= center.x - width / 2 - 2 && point.x <= center.x + width / 2 + 2
        && point.y >= center.y - height / 2 - 2 && point.y <= center.y + height / 2 + 2
    }
    return Math.abs(point.x - item.x) <= 10 && Math.abs(point.y - item.y) <= 12
  })
}

function lineDistance(point: { x: number; y: number }, item: LayoutItem) {
  const x1 = item.x
  const y1 = item.y
  const x2 = Number(item.x2 ?? item.x)
  const y2 = Number(item.y2 ?? item.y)
  const dx = x2 - x1
  const dy = y2 - y1
  const lengthSquared = dx * dx + dy * dy
  if (!lengthSquared) return Math.hypot(point.x - x1, point.y - y1)
  const t = Math.max(0, Math.min(1, ((point.x - x1) * dx + (point.y - y1) * dy) / lengthSquared))
  const projectionX = x1 + t * dx
  const projectionY = y1 + t * dy
  return Math.hypot(point.x - projectionX, point.y - projectionY)
}

function lineHitBox(item: LayoutItem) {
  const x2 = Number(item.x2 ?? item.x)
  const y2 = Number(item.y2 ?? item.y)
  const x = Math.max(Math.min(item.x, x2) - 8, 0)
  const y = Math.max(Math.min(item.y, y2) - 8, 0)
  return {
    x,
    y,
    width: Math.min(Math.max(Math.abs(x2 - item.x), 1) + 16, 100 - x),
    height: Math.min(Math.max(Math.abs(y2 - item.y), 1) + 16, 100 - y)
  }
}

function transformLayoutPoint(item: LayoutItem, point: { x: number; y: number }) {
  const center = itemCenter(item)
  const scale = scaleValue(item.scale)
  const angle = rotationValue(item.rotation) * Math.PI / 180
  const dx = (point.x - center.x) * scale
  const dy = (point.y - center.y) * scale
  return {
    x: clampPercent(center.x + dx * Math.cos(angle) - dy * Math.sin(angle)),
    y: clampPercent(center.y + dx * Math.sin(angle) + dy * Math.cos(angle))
  }
}

function inverseLayoutPoint(item: LayoutItem, point: { x: number; y: number }) {
  const center = itemCenter(item)
  const scale = scaleValue(item.scale)
  const angle = -rotationValue(item.rotation) * Math.PI / 180
  const dx = point.x - center.x
  const dy = point.y - center.y
  return {
    x: clampPercent(center.x + (dx * Math.cos(angle) - dy * Math.sin(angle)) / scale),
    y: clampPercent(center.y + (dx * Math.sin(angle) + dy * Math.cos(angle)) / scale)
  }
}

function lineEndpointHandleStyle(item: LayoutItem, endpoint: 'start' | 'end') {
  const source = endpoint === 'start'
    ? { x: item.x, y: item.y }
    : { x: Number(item.x2 ?? item.x), y: Number(item.y2 ?? item.y) }
  const point = transformLayoutPoint(item, source)
  return {
    left: `${point.x}%`,
    top: `${point.y}%`
  }
}

function layoutItemGroup(item: LayoutItem) {
  return item.groupId ? layoutForm.layout_items.filter((entry) => entry.groupId === item.groupId) : [item]
}

function itemGeometryPoints(item: LayoutItem) {
  if (item.kind === 'line') {
    return [
      { x: item.x, y: item.y },
      { x: Number(item.x2 ?? item.x), y: Number(item.y2 ?? item.y) }
    ]
  }
  if (item.kind === 'block') {
    const width = Number(item.width ?? 5)
    const height = Number(item.height ?? 5)
    return [
      { x: item.x, y: item.y },
      { x: item.x + width, y: item.y + height }
    ]
  }
  if (isScalableMark(item)) {
    const width = isSidePatternStack(item) ? 10 : 8
    const height = isSidePatternStack(item) ? 24 : 18
    return [
      { x: item.x - width / 2, y: item.y - height / 2 },
      { x: item.x + width / 2, y: item.y + height / 2 }
    ]
  }
  const width = Math.max(8, String(item.symbol || '').length * 4 + 5)
  const height = 8
  return [
    { x: item.x - width / 2, y: item.y - height / 2 },
    { x: item.x + width / 2, y: item.y + height / 2 }
  ]
}

function itemBounds(item: LayoutItem) {
  const points = layoutItemGroup(item).flatMap((entry) => itemGeometryPoints(entry))
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  return {
    left: minX,
    top: minY,
    width: Math.max(maxX - minX, 4),
    height: Math.max(maxY - minY, 4)
  }
}

function itemCenter(item: LayoutItem) {
  const bounds = itemBounds(item)
  return {
    x: bounds.left + bounds.width / 2,
    y: bounds.top + bounds.height / 2
  }
}

function layoutItemSnapshot(item: LayoutItem) {
  return {
    id: item.id,
    kind: item.kind,
    x: Number(item.x ?? 0),
    y: Number(item.y ?? 0),
    x2: item.x2 === undefined ? undefined : Number(item.x2),
    y2: item.y2 === undefined ? undefined : Number(item.y2),
    width: item.width === undefined ? undefined : Number(item.width),
    height: item.height === undefined ? undefined : Number(item.height),
    rotation: rotationValue(item.rotation)
  }
}

function rotatePointAround(point: { x: number; y: number }, center: { x: number; y: number }, degrees: number) {
  const radians = degrees * Math.PI / 180
  const dx = point.x - center.x
  const dy = point.y - center.y
  return {
    x: clampPercent(center.x + dx * Math.cos(radians) - dy * Math.sin(radians)),
    y: clampPercent(center.y + dx * Math.sin(radians) + dy * Math.cos(radians))
  }
}

function rotateLayoutGroupFromSnapshot(target: LayoutItem, dragging: NonNullable<typeof draggingLayoutItem.value>, nextRotation: number) {
  const snapshots = dragging.startItems || []
  const delta = nextRotation - dragging.startRotation
  const center = { x: dragging.centerX, y: dragging.centerY }
  snapshots.forEach((snapshot) => {
    const item = layoutForm.layout_items.find((entry) => entry.id === snapshot.id)
    if (!item) return
    if (snapshot.kind === 'line') {
      const start = rotatePointAround({ x: snapshot.x, y: snapshot.y }, center, delta)
      const end = rotatePointAround({ x: Number(snapshot.x2 ?? snapshot.x), y: Number(snapshot.y2 ?? snapshot.y) }, center, delta)
      item.x = start.x
      item.y = start.y
      item.x2 = end.x
      item.y2 = end.y
      item.rotation = snapshot.rotation
      return
    }
    if (snapshot.kind === 'block') {
      const width = Number(snapshot.width ?? item.width ?? 5)
      const height = Number(snapshot.height ?? item.height ?? 5)
      const rotated = rotatePointAround({ x: snapshot.x + width / 2, y: snapshot.y + height / 2 }, center, delta)
      item.x = clampPercent(rotated.x - width / 2)
      item.y = clampPercent(rotated.y - height / 2)
      item.rotation = rotationValue(snapshot.rotation + delta)
      return
    }
    const rotated = rotatePointAround({ x: snapshot.x, y: snapshot.y }, center, delta)
    item.x = rotated.x
    item.y = rotated.y
    item.rotation = rotationValue(snapshot.rotation + delta)
  })
  if (!snapshots.length) {
    setLayoutGroupTransform(target, 'rotation', nextRotation)
  }
}

function svgItemTransform(item: LayoutItem) {
  const center = itemCenter(item)
  return `translate(${center.x} ${center.y}) rotate(${rotationValue(item.rotation)}) scale(${scaleValue(item.scale)}) translate(${-center.x} ${-center.y})`
}

function selectionBoxStyle(item: LayoutItem) {
  const bounds = itemBounds(item)
  const center = itemCenter(item)
  const width = Math.max(bounds.width * itemScaleX(item), 6)
  const height = Math.max(bounds.height * itemScaleY(item), 6)
  return {
    left: `${clampPercent(center.x - width / 2)}%`,
    top: `${clampPercent(center.y - height / 2)}%`,
    width: `${Math.min(width, 100)}%`,
    height: `${Math.min(height, 100)}%`,
    transform: `rotate(${rotationValue(item.rotation)}deg)`
  }
}

function handleLayoutPointerMove(event: PointerEvent) {
  const dragging = draggingLayoutItem.value
  if (!dragging) return
  const point = layoutPoint(event)
  const dx = point.x - dragging.lastX
  const dy = point.y - dragging.lastY
  const target = layoutForm.layout_items.find((item) => item.id === dragging.id)
  if (!target) return
  if (dragging.mode === 'move') {
    const movableItems = layoutItemGroup(target)
    movableItems.forEach((item) => moveLayoutItem(item, dx, dy))
  } else if (dragging.mode === 'draw-block' && target.kind === 'block') {
    updateDrawnBlock(target, dragging, point)
  } else if (dragging.mode === 'draw-cross') {
    updateDrawnCross(target, dragging, point)
  } else if (dragging.mode === 'resize') {
    const startDistance = Math.max(Math.hypot(dragging.startX - dragging.centerX, dragging.startY - dragging.centerY), 1)
    const nextDistance = Math.max(Math.hypot(point.x - dragging.centerX, point.y - dragging.centerY), 1)
    setLayoutGroupTransform(target, 'scale', scaleValue(dragging.startScale * (nextDistance / startDistance)))
  } else if (dragging.mode === 'line-start' && target.kind === 'line') {
    const nextPoint = inverseLayoutPoint(target, point)
    target.x = nextPoint.x
    target.y = nextPoint.y
  } else if (dragging.mode === 'line-end' && target.kind === 'line') {
    const nextPoint = inverseLayoutPoint(target, point)
    target.x2 = nextPoint.x
    target.y2 = nextPoint.y
  } else {
    const startAngle = Math.atan2(dragging.startY - dragging.centerY, dragging.startX - dragging.centerX) * 180 / Math.PI
    const nextAngle = Math.atan2(point.y - dragging.centerY, point.x - dragging.centerX) * 180 / Math.PI
    const nextRotation = rotationValue(dragging.startRotation + nextAngle - startAngle)
    if (layoutItemGroup(target).length > 1) {
      rotateLayoutGroupFromSnapshot(target, dragging, nextRotation)
    } else {
      setLayoutGroupTransform(target, 'rotation', nextRotation)
    }
  }
  draggingLayoutItem.value = { ...dragging, lastX: point.x, lastY: point.y }
}

function handleLayoutPointerUp() {
  const dragging = draggingLayoutItem.value
  if (dragging) {
    const target = layoutForm.layout_items.find((item) => item.id === dragging.id)
    if (target && dragging.mode === 'draw-block' && target.kind === 'block') finalizeDrawnBlock(target, dragging)
    if (target && dragging.mode === 'draw-cross') finalizeDrawnCross(target, dragging)
    if (dragging.mode === 'draw-block' || dragging.mode === 'draw-cross') activeTool.value = 'select'
  }
  draggingLayoutItem.value = null
  window.removeEventListener('pointermove', handleLayoutPointerMove)
  window.removeEventListener('pointerup', handleLayoutPointerUp)
}

function updateDrawnBlock(item: LayoutItem, dragging: NonNullable<typeof draggingLayoutItem.value>, point: { x: number; y: number }) {
  const x1 = dragging.startX
  const y1 = dragging.startY
  const x2 = point.x
  const y2 = point.y
  const rawHeight = Math.abs(y2 - y1)
  item.x = clampPercent(Math.min(x1, x2))
  item.y = clampPercent(rawHeight < 2 ? y1 - 1 : Math.min(y1, y2))
  item.width = Math.max(Math.abs(x2 - x1), 0.4)
  item.height = Math.max(rawHeight, 2)
}

function finalizeDrawnBlock(item: LayoutItem, dragging: NonNullable<typeof draggingLayoutItem.value>) {
  if (Number(item.width || 0) < 1) {
    item.x = clampPercent(dragging.startX - 5)
    item.width = 10
  }
  if (Number(item.height || 0) < 2) {
    item.y = clampPercent(dragging.startY - 1)
    item.height = 2
  }
}

function updateDrawnCross(item: LayoutItem, dragging: NonNullable<typeof draggingLayoutItem.value>, point: { x: number; y: number }) {
  const group = layoutItemGroup(item)
  const halfSize = Math.max(Math.abs(point.x - dragging.startX), Math.abs(point.y - dragging.startY), 4)
  group.forEach((entry) => {
    if (entry.kind !== 'line') return
    if (entry.id.endsWith('-h')) {
      entry.x = clampPercent(dragging.startX - halfSize)
      entry.y = dragging.startY
      entry.x2 = clampPercent(dragging.startX + halfSize)
      entry.y2 = dragging.startY
    } else {
      entry.x = dragging.startX
      entry.y = clampPercent(dragging.startY - halfSize)
      entry.x2 = dragging.startX
      entry.y2 = clampPercent(dragging.startY + halfSize)
    }
  })
}

function finalizeDrawnCross(item: LayoutItem, dragging: NonNullable<typeof draggingLayoutItem.value>) {
  const bounds = itemBounds(item)
  if (bounds.width >= 4 || bounds.height >= 4) return
  updateDrawnCross(item, dragging, {
    x: clampPercent(dragging.startX + 4),
    y: clampPercent(dragging.startY + 4)
  })
}

function moveLayoutItem(item: LayoutItem, dx: number, dy: number) {
  item.x = clampPercent(item.x + dx)
  item.y = clampPercent(item.y + dy)
  if (item.kind === 'line') {
    item.x2 = clampPercent(Number(item.x2 ?? item.x) + dx)
    item.y2 = clampPercent(Number(item.y2 ?? item.y) + dy)
  }
}

function removeLayoutItem(id: string) {
  const index = layoutForm.layout_items.findIndex((item) => item.id === id)
  if (index >= 0) layoutForm.layout_items.splice(index, 1)
  if (selectedLayoutItemId.value === id) selectedLayoutItemId.value = ''
}

function removeSelectedLayoutItem() {
  const item = selectedLayoutItem.value
  if (item) removeLayoutItem(item.id)
}

function clearLayoutItems() {
  layoutForm.layout_items = []
  activeTool.value = 'select'
  selectedLayoutItemId.value = ''
}

function currentLayoutSettings() {
  return JSON.parse(JSON.stringify({
    ...layoutForm,
    layout_items: layoutForm.layout_items.map((item) => ({ ...item }))
  })) as EntrustLayoutSettings & { layout_items: LayoutItem[] }
}

async function saveLayoutTemplate() {
  if (!sheet.value) return
  const defaultName = String(sheet.value?.customer_name || detailRaw('customer_text') || 'Layout template').trim() || 'Layout template'
  const name = window.prompt('请输入模板名称', defaultName)?.trim()
  if (!name) return
  try {
    await apiClient.post('/sales-orders/entrust-layout-templates', {
      name,
      template_type: 'template',
      order_no: sheet.value.order.order_no,
      settings: currentLayoutSettings()
    })
    ElMessage.success('模板已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function loadLayoutTemplate() {
  try {
    const { data: templates } = await apiClient.get<StoredLayoutTemplate[]>('/sales-orders/entrust-layout-templates', {
      params: { template_type: 'template' }
    })
    if (!templates.length) {
      ElMessage.warning('暂无已保存模板')
      return
    }
    const names = templates
      .map((entry, index) => {
        const orderNo = entry.order_no ? ` / ${entry.order_no}` : ''
        const createdAt = entry.created_at ? ` / ${dateTimeText(entry.created_at, '')}` : ''
        return `${index + 1}. ${entry.name}${orderNo}${createdAt}`
      })
      .join('\n')
    const input = window.prompt(`请输入要调取的模板编号或名称：\n${names}`, '1')?.trim()
    if (!input) return
    const selectedIndex = Number(input)
    const template = Number.isInteger(selectedIndex)
      ? templates[selectedIndex - 1]
      : templates.find((entry) => entry.name === input)
    if (!template) {
      ElMessage.error('未找到该模板')
      return
    }
    applyLayoutSettings(template.settings)
    activeTool.value = 'select'
    selectedLayoutItemId.value = ''
    ElMessage.success('模板已调取')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function archiveCurrentLayout() {
  if (!sheet.value) return
  const orderNo = sheet.value?.order.order_no || 'unknown-order'
  const stamp = new Date().toLocaleString('zh-CN', { hour12: false })
  try {
    await apiClient.post('/sales-orders/entrust-layout-templates', {
      name: `${orderNo} ${stamp}`,
      template_type: 'archive',
      order_no: orderNo,
      settings: currentLayoutSettings()
    })
    ElMessage.success('已存档当前排版')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function wipeLayoutItems() {
  if (!layoutForm.layout_items.length) return
  clearLayoutItems()
  ElMessage.success('已清空加入的图案')
}

function syncSelectedGroupTransform(field: 'rotation' | 'scale' | 'scaleX' | 'scaleY') {
  const item = selectedLayoutItem.value
  if (!item) return
  const value = field === 'rotation'
    ? rotationValue(item.rotation)
    : field === 'scale'
      ? scaleValue(item.scale)
      : field === 'scaleY'
      ? axisScaleValue(item.scaleY, 12)
      : axisScaleValue(item.scaleX, 12)
  setLayoutGroupTransform(item, field, value)
}

function setLayoutGroupTransform(item: LayoutItem, field: 'rotation' | 'scale' | 'scaleX' | 'scaleY', value: number) {
  layoutItemGroup(item).forEach((entry) => {
    entry[field] = value
  })
}

function layoutItemStyle(item: LayoutItem) {
  return {
    left: `${Math.max(4, Math.min(Number(item.x ?? 50), 96))}%`,
    top: `${Math.max(4, Math.min(Number(item.y ?? 50), 96))}%`,
    transform: `translate(-50%, -50%) rotate(${rotationValue(item.rotation)}deg) scale(${itemScaleX(item)}, ${itemScaleY(item)})`
  }
}

function normalizeLayoutItem(item: Record<string, string | number | boolean>, index: number): LayoutItem {
  const type = String(item.type || 'text')
  const groupId = item.groupId === undefined ? undefined : String(item.groupId)
  const isAutoSidePatternStack = type.includes('side_pattern_mark_stack') && String(groupId || '').startsWith('auto-side-pattern')
  const inferredLineTypes = [
    'arrow_left',
    'arrow_right',
    'arrow_up',
    'arrow_down',
    'arrow_up_left',
    'arrow_up_right',
    'arrow_down_left',
    'arrow_down_right',
    'double_arrow',
    'cross',
    'horizontal_line',
    'vertical_line',
    'parallel_lines',
    'corner_left',
    'corner_bottom',
    'tee_line',
    'dashed_line',
    'inspection_line'
  ]
  const kind = String(item.kind || (inferredLineTypes.includes(type) ? 'line' : type === 'solid_block' ? 'block' : 'mark')) as LayoutItem['kind']
  return {
    id: String(item.id || `saved-${index}`),
    kind,
    type,
    label: String(item.label || type || 'mark'),
    symbol: String(item.symbol || (kind === 'line' ? '-' : 'T')),
    x: Number(item.x ?? 50),
    y: isAutoSidePatternStack ? 70 : Number(item.y ?? 50),
    x2: item.x2 === undefined ? undefined : Number(item.x2),
    y2: item.y2 === undefined ? undefined : Number(item.y2),
    width: item.width === undefined ? undefined : Number(item.width),
    height: item.height === undefined ? undefined : Number(item.height),
    strokeWidth: item.strokeWidth === undefined ? undefined : Number(item.strokeWidth),
    dashed: Boolean(item.dashed),
    arrow: Boolean(item.arrow),
    arrowStart: Boolean(item.arrowStart),
    rotation: rotationValue(Number(item.rotation ?? 0)),
    scale: scaleValue(Number(item.scale ?? 1)),
    scaleX: isAutoSidePatternStack
      ? 1
      : item.scaleX === undefined ? (type.includes('flag_mark') || type.includes('side_pattern_mark_stack') ? 1 : undefined) : axisScaleValue(Number(item.scaleX), 12),
    scaleY: isAutoSidePatternStack
      ? 1.05
      : item.scaleY === undefined ? (type.includes('flag_mark') ? 1.25 : type.includes('side_pattern_mark_stack') ? 1 : undefined) : axisScaleValue(Number(item.scaleY), 12),
    groupId
  }
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function applyLayoutSettings(settings?: EntrustLayoutSettings) {
  const next = settings || {}
  layoutForm.title_mode = String(next.title_mode || details.value.order_type || 'new_cylinder')
  const nextDiagramStyle = String(next.diagram_style || 'three_section')
  layoutForm.diagram_style = ['three_section', 'single_window'].includes(nextDiagramStyle) ? nextDiagramStyle : 'three_section'
  layoutForm.color_columns = Number(next.color_columns || 13)
  layoutForm.show_info_table = next.show_info_table ?? true
  layoutForm.show_color_table = next.show_color_table ?? true
  layoutForm.show_layout_diagram = next.show_layout_diagram ?? true
  layoutForm.show_requirements = false
  layoutForm.left_label = String(next.left_label || '')
  layoutForm.center_label = String(next.center_label || '')
  layoutForm.right_label = String(next.right_label || '')
  layoutForm.top_note = String(next.top_note || '')
  layoutForm.bottom_note = String(next.bottom_note || '')
  layoutForm.width_label = String(next.width_label || '')
  layoutForm.custom_note = String(next.custom_note || '')
  layoutForm.left_mark = String(next.left_mark ?? '')
  layoutForm.empty_move = String(next.empty_move ?? '')
  layoutForm.left_detection = String(next.left_detection ?? '')
  layoutForm.left_empty = String(next.left_empty ?? '')
  layoutForm.empty_color_move = String(next.empty_color_move ?? '')
  layoutForm.layout_color = String(next.layout_color || '')
  layoutForm.left_color = String(next.left_color || next.layout_color || '')
  layoutForm.right_color = String(next.right_color || next.layout_color || '')
  layoutForm.left_broaden = String(next.left_broaden ?? '')
  layoutForm.middle_broaden = Number(next.middle_broaden || 0)
  layoutForm.right_move = String(next.right_move ?? '')
  layoutForm.right_mark = String(next.right_mark ?? next.right_move ?? '')
  layoutForm.right_empty_move = String(next.right_empty_move ?? '')
  layoutForm.right_detection = String(next.right_detection ?? '')
  layoutForm.right_empty = String(next.right_empty ?? '')
  layoutForm.right_broaden = String(next.right_broaden ?? '')
  layoutForm.printing_width = String(next.printing_width ?? '')
  layoutForm.printing_margin = String(next.printing_margin ?? '')
  layoutForm.continuity = Boolean(next.continuity ?? false)
  layoutForm.light_spot_horizontal = Number(next.light_spot_horizontal ?? 1)
  layoutForm.light_spot_vertical = Number(next.light_spot_vertical ?? 1)
  layoutForm.light_spot_width = Number(next.light_spot_width ?? 0)
  layoutForm.pattern_1mm_label = String(next.pattern_1mm_label ?? '')
  layoutForm.pattern_20mm_label = String(next.pattern_20mm_label ?? '')
  layoutForm.light_spot_upper_left = Boolean(next.light_spot_upper_left ?? false)
  layoutForm.light_spot_upper_right = Boolean(next.light_spot_upper_right ?? false)
  layoutForm.light_spot_lower_left = Boolean(next.light_spot_lower_left ?? false)
  layoutForm.light_spot_lower_right = Boolean(next.light_spot_lower_right ?? false)
  layoutForm.left_mark_enabled = Boolean(next.left_mark_enabled ?? true)
  layoutForm.right_mark_enabled = Boolean(next.right_mark_enabled ?? true)
  layoutForm.left_detection_enabled = Boolean(next.left_detection_enabled ?? false)
  layoutForm.right_detection_enabled = Boolean(next.right_detection_enabled ?? false)
  layoutForm.exclusive_use = Boolean(next.exclusive_use ?? false)
  layoutForm.mid_mark = Boolean(next.mid_mark ?? false)
  layoutForm.mid_mark_value = String(next.mid_mark_value ?? next.middle_mark ?? '')
  layoutForm.left_self_mark = Boolean(next.left_self_mark ?? false)
  layoutForm.right_self_mark = Boolean(next.right_self_mark ?? false)
  layoutForm.full_line = Boolean(next.full_line ?? false)
  layoutForm.full_line_width = String(next.full_line_width ?? '')
  layoutForm.layout_items = Array.isArray(next.layout_items)
    ? next.layout_items.map((item, index) => normalizeLayoutItem(item, index))
    : []
  syncSidePatternTextLabels()
}

function applyRequirementForm(source: PlateDetails = {}) {
  requirementKeys.forEach((key) => {
    requirementForm[key] = String(source[key] ?? '')
  })
}

function requirementPayload() {
  return Object.fromEntries(requirementKeys.map((key) => [key, requirementForm[key]]))
}

function entrustNoFromOrder(source: SalesOrder) {
  return value(source.plate_details?.sample_no || source.plate_details?.no || source.order_no)
}

async function loadEntrust() {
  loading.value = true
  try {
    const { data } = await apiClient.get<EntrustSheet>(`/sales-orders/${route.params.id}/entrust`)
    sheet.value = data
    applyLayoutSettings(data.order.plate_details?.entrust_layout)
    applyRequirementForm(data.order.plate_details || {})
    hydrateInlineContent(data.order)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function saveLayout() {
  if (!sheet.value) return
  savingLayout.value = true
  try {
    const { data } = await apiClient.put<SalesOrder>(`/sales-orders/${sheet.value.order.id}/entrust-layout`, { ...layoutForm })
    sheet.value = { ...sheet.value, order: data }
    ElMessage.success('委托书版式已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingLayout.value = false
  }
}

async function saveEntrustContent() {
  if (!sheet.value) return
  savingContent.value = true
  try {
    const { data } = await apiClient.put<SalesOrder>(`/sales-orders/${sheet.value.order.id}/entrust-content`, {
      plate_details: inlineDetailsPayload(),
      color_rows: inlineColorRowsPayload()
    })
    sheet.value = { ...sheet.value, entrust_no: entrustNoFromOrder(data), order: data }
    applyRequirementForm(data.plate_details || {})
    hydrateInlineContent(data)
    ElMessage.success('委托书表格内容已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingContent.value = false
  }
}

async function saveRequirements() {
  if (!sheet.value) return
  savingRequirements.value = true
  try {
    const { data } = await apiClient.put<SalesOrder>(`/sales-orders/${sheet.value.order.id}/entrust-requirements`, requirementPayload())
    sheet.value = { ...sheet.value, entrust_no: entrustNoFromOrder(data), order: data }
    applyRequirementForm(data.plate_details || {})
    hydrateInlineContent(data)
    ElMessage.success('委托书要求已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingRequirements.value = false
  }
}

function createSheetExportClone() {
  const source = document.querySelector('.print-sheet') as HTMLElement | null
  if (!source) return null
  const clone = source.cloneNode(true) as HTMLElement
  clone.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml')
  clone.querySelectorAll('input, textarea, datalist, .no-print').forEach((element) => element.remove())
  clone.querySelectorAll<HTMLElement>('.print-only').forEach((element) => {
    element.style.display = 'inline'
    element.style.whiteSpace = 'pre-wrap'
  })
  clone.querySelectorAll<HTMLElement>('.layout-formula-table').forEach((element) => {
    element.style.display = 'grid'
    element.style.visibility = 'visible'
  })
  clone.style.width = '1180px'
  clone.style.maxWidth = 'none'
  clone.style.margin = '0'
  clone.style.background = '#ffffff'
  return clone
}

async function printSheet() {
  const printWindow = window.open('', '_blank')
  if (sheet.value) {
    try {
      await apiClient.post(`/sales-orders/${sheet.value.order.id}/entrust/print`, { ...layoutForm })
    } catch (error) {
      ElMessage.warning('打印记录保存失败，已继续打开打印窗口')
    }
  }
  await nextTick()
  const printContent = createSheetExportClone()?.outerHTML
  if (printWindow && printContent) {
    const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
      .map((node) => node.outerHTML)
      .join('\n')
    printWindow.document.open()
    printWindow.document.write(`<!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <title>BSPM Entrust Sheet</title>
          ${styles}
          <style>
            @page { size: A4 portrait; margin: 8mm; }
            html, body { margin: 0 !important; background: #ffffff !important; font-family: Arial, sans-serif; }
            body { display: block; }
            .print-sheet { max-width: none !important; width: 100% !important; margin: 0 auto !important; padding: 0 !important; border: 0 !important; box-shadow: none !important; }
            .no-print, .app-aside, .app-header, .el-message, .el-notification, .el-dialog { display: none !important; }
            .print-only { display: inline !important; white-space: pre-wrap !important; }
            .cell-input, .cell-textarea { display: none !important; }
            .layout-formula-table { display: grid !important; visibility: visible !important; }
            .layout-formula-table * { visibility: visible !important; }
            .warrant-layout-box { break-inside: avoid; page-break-inside: avoid; }
            .warrant-layout-box .layout-core { grid-template-rows: 64px 1fr 58px !important; height: 308px !important; box-sizing: border-box !important; padding-right: 0 !important; padding-bottom: 28px !important; overflow: visible !important; }
            .warrant-layout-box .layout-window { min-height: 196px !important; }
            .warrant-layout-box .layout-added-side_pattern_mark_stack,
            .warrant-layout-box .layout-added-side_pattern_mark_stack_right,
            .warrant-layout-box .layout-side-pattern-stack { width: 34px !important; height: 96px !important; }
            .warrant-layout-box .layout-added-side_pattern_text { font-size: 7.2px !important; }
          </style>
        </head>
        <body>
          <section class="entrust-page">${printContent}</section>
        </body>
      </html>`)
    printWindow.document.close()
    printWindow.focus()
    window.setTimeout(() => {
      printWindow.print()
      printWindow.close()
    }, 250)
    return
  }
  const previousTitle = document.title
  const printTitle = 'BSPM Entrust Sheet'
  let restored = false
  const restoreTitle = () => {
    if (restored) return
    restored = true
    document.title = previousTitle
    window.removeEventListener('afterprint', restoreTitle)
    window.removeEventListener('focus', restoreOnFocus)
  }
  const restoreOnFocus = () => {
    window.setTimeout(restoreTitle, 500)
  }
  document.title = printTitle
  window.addEventListener('afterprint', restoreTitle, { once: true })
  window.addEventListener('focus', restoreOnFocus, { once: true })
  window.print()
}

onMounted(loadEntrust)
</script>

<style scoped>
.entrust-page {
  align-items: center;
  font-family: Arial, sans-serif;
}

.print-sheet {
  width: min(100%, 1180px);
  padding: 8px 10px;
  font-family: Arial, sans-serif;
  color: #111827;
  background: #ffffff;
  border: 1px solid #d9dee8;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.warrant-main-title {
  margin: 0 0 5px;
  color: #111827;
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0;
  text-align: center;
}

.layout-controls {
  width: min(100%, 1440px);
  max-width: 100%;
}

.entrust-requirements {
  width: min(100%, 1440px);
  max-width: 100%;
}

.requirement-edit-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 12px 14px;
}

.requirement-edit-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.layout-control-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 12px 14px;
}

.layout-entry-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid #93c5fd;
  border-radius: 8px;
  background: #eff6ff;
  color: #1e3a8a;
}

.layout-entry-banner strong {
  font-size: 16px;
  white-space: nowrap;
}

.layout-entry-banner span {
  font-size: 13px;
  line-height: 1.5;
}

.layout-control-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.wide-field {
  grid-column: span 2;
}

.switch-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
}

.layout-editor {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 12px;
  margin-top: 18px;
  padding: 10px;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid #cfd6e4;
  background: #f7f9fc;
}

.layout-tool-rail {
  display: grid;
  grid-template-columns: repeat(2, 42px);
  gap: 6px;
  align-content: start;
  justify-content: start;
}

.layout-tool-rail .el-button {
  width: 40px;
  height: 38px;
  margin: 0;
  padding: 0;
  border-radius: 2px;
}

.layout-tool-rail .el-button.active {
  border-color: #0f766e;
  color: #0f766e;
  background: #ecfdf5;
}

.tool-svg {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  color: currentColor;
}

.tool-svg :deep(svg) {
  width: 28px;
  height: 28px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: square;
  stroke-linejoin: miter;
}

.layout-editor-main {
  display: grid;
  gap: 10px;
  min-width: 0;
  max-width: 100%;
}

.layout-editor-fields,
.layout-editor-options {
  display: grid;
  grid-template-columns: repeat(8, minmax(116px, 1fr));
  gap: 8px 12px;
  align-items: end;
}

.layout-editor-fields-grouped {
  grid-template-columns: minmax(0, 2fr) minmax(260px, 0.9fr);
  align-items: stretch;
}

.layout-side-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  min-width: 0;
}

.layout-param-column,
.layout-common-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(108px, 1fr));
  gap: 8px 10px;
  align-items: end;
  min-width: 0;
  padding: 8px;
  border: 1px solid #d7deea;
  background: #ffffff;
}

.layout-common-fields {
  grid-template-columns: repeat(2, minmax(112px, 1fr));
}

.layout-column-title {
  grid-column: 1 / -1;
  color: #334155;
  font-size: 12px;
  line-height: 1;
}

.layout-editor-fields label,
.layout-editor-fields .layout-field,
.layout-editor-options label {
  display: grid;
  gap: 3px;
  color: #111827;
  font-size: 11px;
  font-weight: 700;
}

.layout-editor :deep(.el-input__wrapper),
.layout-editor :deep(.el-input-number) {
  width: 100%;
}

.field-with-toggle {
  align-items: stretch;
}

.field-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  min-height: 18px;
  line-height: 1;
  white-space: nowrap;
}

.fill-pattern-mini {
  min-height: 20px;
  margin-left: 4px;
  padding: 2px 7px;
  font-size: 10px;
  line-height: 1;
}

.detection-toggle {
  min-height: 18px;
  margin-right: 0;
  margin-left: 4px;
}

.detection-toggle :deep(.el-checkbox__label) {
  padding-left: 4px;
  font-size: 10px;
  line-height: 1;
}

.mid-mark-control :deep(.el-checkbox) {
  min-height: 40px;
  margin-right: 0;
  align-items: center;
}

.layout-inline-options {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  padding: 8px 10px;
  border: 1px solid #d8dee9;
  background: #ffffff;
}

.layout-inline-options :deep(.el-checkbox) {
  min-height: 24px;
  margin-right: 0;
}

.layout-inline-options :deep(.el-checkbox__label) {
  padding-left: 5px;
  font-size: 11px;
  line-height: 1.1;
}

.layout-blueprint {
  position: relative;
  min-height: 560px;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  border: 2px solid #9aa5b5;
  background:
    linear-gradient(#ffffff, #ffffff) padding-box,
    repeating-linear-gradient(90deg, transparent 0 77px, rgba(17, 24, 39, 0.08) 78px 79px),
    repeating-linear-gradient(0deg, transparent 0 54px, rgba(17, 24, 39, 0.08) 55px 56px);
}

.blueprint-left-marks {
  position: absolute;
  left: 26px;
  top: 78px;
  z-index: 2;
  display: grid;
  gap: 5px;
  width: 34px;
  padding-top: 16px;
  border-left: 2px dashed #111827;
  color: #e00000;
  font: 700 18px Arial, sans-serif;
  text-align: center;
}

.blueprint-top-line {
  display: none;
  position: absolute;
  top: 14px;
  left: 46px;
  right: 38px;
  grid-template-columns: repeat(9, minmax(86px, 1fr));
  gap: 8px;
  align-items: center;
  color: #e00000;
  font: 700 12px Arial, sans-serif;
}

.blueprint-top-line b {
  display: block;
  margin-top: 2px;
  font-size: 20px;
}

.blueprint-top-line em {
  color: #111827;
  font-style: normal;
  font-size: 12px;
}

.blueprint-panel {
  position: absolute;
  inset: 62px 104px 158px 44px;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
}

.blueprint-window {
  position: relative;
  display: grid;
  min-width: 0;
  border: 0;
  border-top: 2px solid #111827;
  border-bottom: 2px solid #111827;
  background: #fff;
}

.blueprint-section {
  position: relative;
  display: grid;
  place-items: center;
  min-width: 0;
  border-right: 2px solid #111827;
  font: 700 22px Arial, sans-serif;
}

.blueprint-section.center {
  font-size: 26px;
}

.blueprint-section.side-space {
  color: transparent;
  pointer-events: none;
}

.side-box {
  position: relative;
  overflow: hidden;
  background: #ffffff;
}

.left-side-box,
.left-side-box.has-mark-line {
  border-left: 2px solid #111827;
}

.right-side-box {
  border-right: 2px solid #111827;
}

.right-side-box.has-mark-line {
  border-right: 2px solid #111827;
}

.layout-inner-line {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 4;
  display: block;
  pointer-events: none;
}

.layout-inner-line.detection-line {
  width: 4px;
  min-width: 4px;
  background: #111827;
}

.layout-inner-line.detection-line.left {
  transform: none;
}

.layout-inner-line.detection-line.right {
  transform: none;
}

.blueprint-section:last-of-type {
  border-right: 0;
}

.blueprint-section.right-side-box,
.blueprint-section.right-side-box.has-mark-line {
  border-right: 2px solid #111827;
}

.layout-broaden-label {
  position: absolute;
  bottom: -58px;
  z-index: 14;
  color: #e00000;
  font: 700 14px Arial, sans-serif;
  white-space: nowrap;
  transform: translateX(-50%);
}

.layout-broaden-label.right {
  transform: translateX(50%);
}

.layout-broaden-label::before {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 2px);
  height: 24px;
  border-left: 2px solid #e00000;
  content: "";
  transform: translateX(-50%);
}

.layout-broaden-label::after {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 24px);
  width: 0;
  height: 0;
  border-right: 5px solid transparent;
  border-bottom: 8px solid #e00000;
  border-left: 5px solid transparent;
  content: "";
  transform: translateX(-50%);
}

.middle-grid-section,
.middle-print-section {
  padding: 0;
}

.middle-grid {
  position: relative;
  z-index: 0;
  display: grid;
  width: 100%;
  height: 100%;
  min-height: 140px;
  overflow: hidden;
  background: #ffffff;
  cursor: default;
}

.layout-edge-ticks {
  position: absolute;
  left: 0;
  right: 0;
  z-index: 5;
  height: 8px;
  pointer-events: none;
}

.layout-edge-ticks.top {
  top: 0;
}

.layout-edge-ticks.bottom {
  bottom: 0;
}

.layout-edge-ticks i {
  position: absolute;
  width: 1.5px;
  height: 8px;
  background: #111827;
  transform: translateX(-50%);
}

.layout-edge-ticks.bottom i {
  bottom: 0;
}

.layout-dimension-arrow {
  position: absolute;
  z-index: 13;
  display: grid;
  color: #e00000;
  font: 800 12px/1.1 Arial, sans-serif;
  pointer-events: none;
}

.layout-dimension-arrow strong {
  display: inline-grid;
  place-items: center;
  justify-self: center;
  padding: 1px 4px;
  border: 1px solid rgba(224, 0, 0, 0.34);
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.75);
  white-space: nowrap;
}

.dimension-line {
  position: relative;
  display: block;
}

.dimension-line.horizontal {
  align-self: center;
  width: 100%;
  height: 0;
  border-top: 2px solid #e00000;
}

.dimension-line.horizontal::before,
.dimension-line.horizontal::after {
  position: absolute;
  top: -5px;
  width: 0;
  height: 0;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  content: "";
}

.dimension-line.horizontal::before {
  left: 0;
  border-right: 7px solid #e00000;
}

.dimension-line.horizontal::after {
  right: 0;
  border-left: 7px solid #e00000;
}

.dimension-line.vertical {
  justify-self: center;
  width: 0;
  height: 100%;
  border-left: 2px solid #e00000;
}

.dimension-line.vertical::before,
.dimension-line.vertical::after {
  position: absolute;
  left: -5px;
  width: 0;
  height: 0;
  border-right: 4px solid transparent;
  border-left: 4px solid transparent;
  content: "";
}

.dimension-line.vertical::before {
  top: 0;
  border-bottom: 7px solid #e00000;
}

.dimension-line.vertical::after {
  bottom: 0;
  border-top: 7px solid #e00000;
}

.cir-dimension {
  top: 8px;
  right: 8px;
  bottom: 8px;
  width: 48px;
  grid-template-columns: minmax(0, 1fr) 10px;
  gap: 4px;
  align-items: center;
}

.cir-dimension .dimension-line {
  grid-column: 2;
  grid-row: 1;
}

.cir-dimension strong {
  grid-column: 1;
  grid-row: 1;
  justify-self: end;
  writing-mode: vertical-rl;
  transform: rotate(180deg);
}

.width-dimension {
  bottom: -34px;
  height: 30px;
  grid-template-rows: 10px 18px;
  gap: 2px;
  align-items: end;
  text-align: center;
}

.layout-drawing-layer {
  position: absolute;
  inset: 0;
  z-index: 11;
  overflow: visible;
  cursor: crosshair;
  touch-action: none;
}

.layout-near-label {
  position: absolute;
  z-index: 12;
  display: inline-grid;
  place-items: center;
  min-width: 32px;
  padding: 1px 3px;
  border: 1px solid rgba(224, 0, 0, 0.34);
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.92);
  color: #e00000;
  font: 800 10px/1.05 Arial, sans-serif;
  pointer-events: none;
  transform: translateX(-50%);
  white-space: nowrap;
}

.layout-near-label.align-left {
  transform: none;
}

.layout-near-label.align-right {
  transform: translateX(-100%);
}

.layout-drawing-layer.is-selecting {
  cursor: default;
}

.layout-drawing-layer:focus {
  outline: 2px solid rgba(37, 99, 235, 0.24);
  outline-offset: -2px;
}

.print-drawing-layer {
  z-index: 6;
  overflow: hidden;
  pointer-events: none;
}

.middle-grid-cell {
  min-width: 0;
  min-height: 0;
  border-right: var(--grid-line-width, 2px) solid #111827;
  border-bottom: var(--grid-line-width, 2px) solid #111827;
}

.middle-grid-cell.is-last-col {
  border-right: 0;
}

.middle-grid-cell.is-last-row {
  border-bottom: 0;
}

.middle-grid-value {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-items: center;
  color: #e00000;
  font: 700 26px Arial, sans-serif;
  pointer-events: none;
}

.layout-generated-layer {
  position: absolute;
  inset: 0;
  z-index: 3;
  width: 100%;
  height: 100%;
  pointer-events: auto;
}

.layout-svg-item {
  cursor: move;
  pointer-events: all;
}

.layout-svg-item.selected {
  filter: drop-shadow(0 0 2px #2563eb);
}

.light-spot,
.layout-added-item {
  position: absolute;
  z-index: 5;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.light-spot {
  width: 10px;
  height: 10px;
  background: #111827;
}

.light-spot.upper-left {
  left: 0;
  top: 0;
  transform: none;
}

.light-spot.upper-right {
  right: 0;
  top: 0;
  transform: none;
}

.light-spot.lower-left {
  left: 0;
  bottom: 0;
  transform: none;
}

.light-spot.lower-right {
  right: 0;
  bottom: 0;
  transform: none;
}

.layout-added-item {
  color: #111827;
  cursor: move;
  font: 800 22px Arial, sans-serif;
  line-height: 1;
  pointer-events: auto;
  text-shadow: 0 0 0 #111827;
}

.layout-added-item.selected {
  color: #2563eb;
  text-shadow: 0 0 2px rgba(37, 99, 235, 0.35);
}

.layout-added-dot_column {
  display: grid;
  gap: 1px;
  color: #e00000;
  font: 800 16px Arial, sans-serif;
  line-height: 1;
  text-align: center;
  white-space: pre-line;
  text-shadow: none;
}

.layout-added-side_pattern_text {
  color: #111827;
  font: 800 11px Arial, sans-serif;
  line-height: 1;
  text-shadow: none;
  white-space: nowrap;
}

.layout-added-side_pattern_dots {
  color: #111827;
  font: 800 8px Arial, sans-serif;
  line-height: 0.86;
  text-align: center;
  text-shadow: none;
  white-space: pre-line;
}

.layout-added-side_pattern_mark_stack,
.layout-added-side_pattern_mark_stack_right {
  display: inline-grid;
  place-items: center;
  width: 48px;
  height: 136px;
  color: #111827;
  font-size: 0;
  text-shadow: none;
}

.layout-side-pattern-stack {
  display: block;
  width: 48px;
  height: 136px;
  overflow: visible;
}

.layout-side-pattern-stack path {
  fill: none;
  stroke: currentColor;
  stroke-width: 3.2;
  stroke-linecap: square;
  stroke-linejoin: miter;
  vector-effect: non-scaling-stroke;
}

.layout-side-pattern-digits circle {
  fill: #ffffff;
  stroke: currentColor;
  stroke-width: 1.7;
  vector-effect: non-scaling-stroke;
}

.layout-side-pattern-digits text {
  fill: currentColor;
  stroke: none;
  font: 700 8px Arial, sans-serif;
  text-anchor: middle;
}

.layout-added-left_flag_mark,
.layout-added-right_flag_mark {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 36px;
  color: #111827;
  font-size: 0;
  text-shadow: none;
}

.layout-added-left_flag_mark.selected,
.layout-added-right_flag_mark.selected {
  color: #111827;
  text-shadow: none;
}

.layout-flag-svg {
  display: block;
  width: 18px;
  height: 36px;
  overflow: visible;
}

.layout-flag-svg path {
  fill: none;
  stroke: currentColor;
  stroke-width: 2.8;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}

.layout-selection-box {
  position: absolute;
  z-index: 14;
  box-sizing: border-box;
  border: 2px solid #2563eb;
  transform-origin: center;
  pointer-events: none;
}

.layout-transform-handle {
  position: absolute;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 2px solid #2563eb;
  border-radius: 0;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.24);
  color: #2563eb;
  font: 800 13px/1 Arial, sans-serif;
  pointer-events: auto;
}

.layout-transform-handle.resize {
  cursor: nwse-resize;
}

.layout-transform-handle.top-left {
  left: -11px;
  top: -11px;
}

.layout-transform-handle.top-right {
  right: -11px;
  top: -11px;
}

.layout-transform-handle.bottom-left {
  left: -11px;
  bottom: -11px;
}

.layout-transform-handle.bottom-right {
  right: -11px;
  bottom: -11px;
}

.layout-transform-handle.rotate {
  left: 50%;
  top: -34px;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  transform: translateX(-50%);
  cursor: grab;
}

.layout-transform-handle.delete {
  top: -34px;
  right: -15px;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-color: #dc2626;
  border-radius: 999px;
  color: #dc2626;
  cursor: pointer;
}

.layout-selection-box::before {
  position: absolute;
  left: 50%;
  top: -18px;
  width: 1px;
  height: 18px;
  background: #2563eb;
  content: "";
}

.layout-line-endpoint-handle {
  position: absolute;
  z-index: 15;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 2px solid #2563eb;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.24);
  cursor: grab;
  pointer-events: auto;
  transform: translate(-50%, -50%);
}

.layout-line-endpoint-handle:active,
.layout-transform-handle.rotate:active {
  cursor: grabbing;
}

.layout-added-text {
  padding: 1px 4px;
  border: 1px solid #111827;
  font-size: 14px;
}

.layout-added-solid_block {
  font-size: 18px;
}

.layout-added-dashed_line {
  min-width: 34px;
  overflow: hidden;
  font-size: 18px;
  letter-spacing: 0;
}

.layout-added-parallel_lines {
  font-size: 26px;
}

.blueprint-right-note {
  display: grid;
  place-items: center;
  border-left: 3px solid #111827;
  border-right: 3px solid #111827;
  color: #e00000;
  font: 700 18px Arial, sans-serif;
  writing-mode: vertical-rl;
}

.blueprint-bottom-line {
  position: absolute;
  left: 84px;
  right: 76px;
  bottom: 74px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 12px;
  align-items: center;
  border-top: 2px solid #111827;
  padding-top: 8px;
  font-size: 13px;
}

.blueprint-bottom-line.engraving-width {
  bottom: 40px;
}

.blueprint-bottom-line.print-width {
  bottom: 12px;
}

.blueprint-bottom-line strong {
  text-align: center;
}

.layout-editor-options {
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 12px 18px;
  align-items: start;
  padding: 6px 0 0;
}

.layout-option-group {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.layout-option-group strong {
  color: #475569;
  font-size: 12px;
  line-height: 1;
}

.option-grid-controls {
  grid-template-columns: repeat(3, minmax(110px, 1fr));
}

.option-grid-controls strong,
.option-grid-controls > :deep(.el-checkbox) {
  grid-column: 1 / -1;
}

.option-check-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px 12px;
}

.option-line-controls {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.option-line-controls strong,
.option-line-controls label {
  grid-column: 1 / -1;
}

.layout-command-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding: 8px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
}

.layout-command-bar .el-button {
  margin-left: 0;
}

.layout-editor-options > *,
.layout-editor-options label {
  min-width: 0;
}

.layout-editor-options :deep(.el-checkbox) {
  margin-right: 0;
  min-height: 28px;
  white-space: normal;
}

.layout-editor-options :deep(.el-checkbox__label) {
  line-height: 1.25;
  white-space: normal;
}

.layout-selected-editor {
  display: grid;
  grid-template-columns: auto repeat(auto-fit, minmax(118px, 1fr)) auto;
  gap: 8px;
  align-items: end;
  padding: 8px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
}

.layout-selected-editor strong {
  align-self: center;
  color: #0f766e;
  font-size: 12px;
  white-space: nowrap;
}

.layout-selected-editor label {
  display: grid;
  gap: 3px;
  color: #111827;
  font-size: 11px;
  font-weight: 700;
}

.layout-item-list {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.sheet-header {
  text-align: center;
  margin-bottom: 8px;
}

.sheet-header h1 {
  margin: 0;
  font-size: 17px;
  letter-spacing: 0;
}

.sheet-header h2 {
  margin: 4px 0 0;
  font-size: 17px;
  letter-spacing: 0;
}

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

th,
td {
  min-height: 24px;
  padding: 4px 5px;
  border: 1px solid #111827;
  font-size: 11.5px;
  line-height: 1.25;
  text-align: center;
  vertical-align: middle;
  overflow-wrap: anywhere;
}

th {
  font-weight: 600;
  color: #0f172a;
  background: #f8fafc;
}

.warrant-table {
  border: 2px solid #111827;
  background: #ffffff;
}

.warrant-table th,
.warrant-table td {
  height: 32px;
  padding: 2px 4px;
  border-color: #111827;
  background: #ffffff;
  font-size: 11px;
  line-height: 1.08;
}

.warrant-table th {
  color: #111827;
  font-weight: 700;
}

.warrant-table .warrant-label-col {
  width: 76px;
}

.warrant-table .warrant-qty-col {
  width: 58px;
}

.warrant-top-row th,
.warrant-top-row td {
  height: 28px;
  border-top: 0;
  border-right: 0;
  border-left: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  text-align: left;
  vertical-align: middle;
}

.warrant-top-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  white-space: nowrap;
}

.warrant-top-line > span:first-child {
  flex: 0 0 auto;
  color: #111827;
  font-weight: 700;
}

.warrant-top-line > strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.warrant-top-line :deep(.cell-input) {
  width: 100%;
  min-width: 0;
  text-align: left;
}

.warrant-info-row th {
  font-size: 11.5px;
  line-height: 1.05;
}

.warrant-layout-title th {
  height: 32px;
  font-size: 18px;
  letter-spacing: 0;
}

.warrant-layout-cell {
  padding: 7px 8px 4px;
}

.layout-box.warrant-layout-box {
  display: grid;
  gap: 6px;
  min-height: 324px;
  margin: 0;
}

.warrant-layout-box .layout-core {
  grid-template-rows: 64px 1fr 58px;
  height: 308px;
  box-sizing: border-box;
  padding-right: 0;
  padding-bottom: 34px;
}

.warrant-layout-box .layout-top {
  display: block;
  overflow: visible;
  padding: 0;
  color: #e00000;
  font: 800 12px/1.1 Arial, sans-serif;
  text-align: center;
}

.warrant-layout-box .layout-top-guide {
  position: absolute;
  z-index: 16;
  display: inline-grid;
  place-items: center;
  min-width: 42px;
  padding: 1px 4px;
  border: 1px solid rgba(224, 0, 0, 0.34);
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.75);
  white-space: nowrap;
  transform: translateX(-50%);
}

.warrant-layout-box .layout-top-guide::after {
  position: absolute;
  left: 50%;
  top: calc(100% + 1px);
  height: 12px;
  border-left: 1.6px solid #e00000;
  content: "";
  transform: translateX(-50%);
}

.warrant-layout-box .layout-top-guide::before {
  position: absolute;
  left: 50%;
  top: calc(100% + 12px);
  width: 0;
  height: 0;
  border-right: 4px solid transparent;
  border-left: 4px solid transparent;
  border-top: 6px solid #e00000;
  content: "";
  transform: translateX(-50%);
}

.warrant-layout-box .layout-window {
  min-height: 208px;
  border-width: 2px;
}

.warrant-layout-box .layout-section {
  border-right-width: 2px;
}

.warrant-layout-box .layout-near-label {
  display: none;
}

.warrant-layout-box .layout-added-side_pattern_mark_stack,
.warrant-layout-box .layout-added-side_pattern_mark_stack_right,
.warrant-layout-box .layout-side-pattern-stack {
  width: 34px;
  height: 96px;
}

.warrant-layout-box .layout-added-side_pattern_text {
  font-size: 7.2px;
}

.warrant-layout-box .layout-bottom {
  font-size: 10px;
}

.layout-formula-table {
  display: grid;
  gap: 2px;
  color: #111827;
  font-size: 10.5px;
  line-height: 1.1;
}

.layout-formula-table > div {
  display: grid;
  grid-template-columns: 145px minmax(0, 1fr) 72px;
  gap: 8px;
  align-items: center;
  min-height: 20px;
  border-top: 2px solid #111827;
  text-align: center;
}

.layout-formula-table > div > span:first-child {
  text-align: right;
}

.layout-formula-table > div > span:last-child {
  text-align: left;
}

.layout-formula-table strong {
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: center;
}

.requirement-value {
  height: 48px;
  text-align: left;
}

.requirement-value .cell-textarea {
  min-height: 42px;
}

.value {
  font-family: Arial, sans-serif;
}

.print-only {
  display: none;
}

:deep(.print-only) {
  display: none;
}

.cell-input,
.cell-textarea,
:deep(.cell-input),
:deep(.cell-textarea) {
  display: block;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  margin: 0;
  padding: 2px 4px;
  border: 1px solid #9ca3af;
  border-radius: 2px;
  outline: 0;
  box-sizing: border-box;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: inherit;
  line-height: inherit;
  text-align: center;
}

.cell-input:focus,
.cell-textarea:focus,
:deep(.cell-input:focus),
:deep(.cell-textarea:focus) {
  background: #fff7ed;
  box-shadow: inset 0 0 0 1px #f97316;
}

.cell-input-compact,
:deep(.cell-input-compact) {
  padding-inline: 0;
  font-size: 10.5px;
}

.cell-textarea,
:deep(.cell-textarea) {
  min-height: 42px;
  resize: vertical;
  text-align: left;
  white-space: pre-wrap;
}

.strong {
  font-weight: 700;
}

.red {
  color: #e00000;
  font-weight: 700;
}

.color-table,
.requirement-table {
  margin-top: 7px;
}

.info-table th {
  width: 10%;
  white-space: nowrap;
}

.info-table td {
  width: 23%;
}

.portrait-info-table {
  display: none;
}

.color-table th:first-child,
.color-table td:first-child {
  width: 82px;
}

.color-table th:last-child,
.color-table td:last-child {
  width: 62px;
}

.layout-title {
  margin: 9px 0 3px;
  font-size: 22px;
  line-height: 1;
  text-align: center;
}

.layout-box {
  position: relative;
  display: block;
  min-height: 286px;
  margin: 0 18px 14px;
  border-bottom: 0;
}

.layout-core {
  display: grid;
  grid-template-rows: 52px 1fr 54px;
  height: 286px;
  border: 0;
}

.layout-top,
.layout-bottom {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11.5px;
}

.layout-bottom {
  flex-direction: column;
  gap: 2px;
  align-items: stretch;
}

.layout-bottom > div {
  display: grid;
  grid-template-columns: 140px 1fr 70px;
  gap: 8px;
  align-items: center;
  text-align: center;
}

.layout-bottom > div > span:first-child {
  text-align: right;
}

.layout-bottom > div > span:last-child {
  text-align: left;
}

.layout-window {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr;
  border: 0;
  border-top: 2px solid #111827;
  border-bottom: 2px solid #111827;
}

.layout-single_window .layout-window {
  grid-template-columns: 1fr;
}

.layout-section {
  display: grid;
  place-items: center;
  border-right: 2px solid #111827;
  font-family: Arial, sans-serif;
}

.middle-print-section {
  display: block;
}

.middle-print-section .middle-grid {
  min-height: 100%;
}

.layout-section-full {
  min-height: 130px;
  border-right: 0;
  font-size: 18px;
  line-height: 1.45;
  padding: 12px;
  white-space: pre-wrap;
}

.layout-section:last-of-type {
  border-right: 0;
}

.layout-section.right-side-box {
  border-right: 0;
}

.layout-section.right-side-box.has-mark-line {
  border-right: 2px solid #111827;
}

.side-label {
  display: grid;
  place-items: center;
  color: #e00000;
  font-family: Arial, sans-serif;
  font-weight: 700;
}

.left-label {
  border-right: 0;
}

.right-label {
  border-left: 0;
}

.requirement-table th {
  width: 128px;
}

.layout-note-table {
  margin: 0 0 14px;
}

.layout-note-table th {
  width: 170px;
}

.layout-note-table td {
  height: 90px;
  padding: 10px 12px;
  text-align: left;
  white-space: pre-wrap;
}

.requirement-table td {
  height: 54px;
  text-align: left;
  padding-left: 12px;
}

@media (max-width: 800px) {
  .print-sheet {
    padding: 18px;
    overflow-x: auto;
  }

  .layout-box {
    margin-inline: 0;
  }

  .layout-control-form,
  .requirement-edit-form {
    grid-template-columns: 1fr;
  }

  .layout-entry-banner {
    align-items: flex-start;
    flex-direction: column;
  }

  .layout-editor {
    grid-template-columns: 1fr;
  }

  .layout-tool-rail {
    grid-template-columns: repeat(8, 40px);
    overflow-x: auto;
  }

  .layout-editor-fields,
  .layout-editor-options {
    grid-template-columns: 1fr;
  }

  .layout-side-fields,
  .layout-param-column,
  .layout-common-fields {
    grid-template-columns: 1fr;
  }

  .layout-blueprint {
    min-width: 760px;
  }

  .layout-editor-main {
    overflow-x: auto;
  }

  .wide-field {
    grid-column: auto;
  }
}

@media print {
  @page {
    size: A4 portrait;
    margin: 8mm;
  }

  :global(html),
  :global(body) {
    width: 100%;
    margin: 0 !important;
    background: #ffffff !important;
  }

  :global(.app-aside),
  :global(.app-header),
  :global(.el-message),
  :global(.el-notification),
  :global(.el-dialog),
  .cell-input,
  .cell-textarea,
  :deep(.cell-input),
  :deep(.cell-textarea),
  .no-print {
    display: none !important;
  }

  .print-only {
    display: inline !important;
    white-space: pre-wrap !important;
  }

  :deep(.print-only) {
    display: inline !important;
    white-space: pre-wrap !important;
  }

  :global(.app-shell),
  :global(.app-shell > .el-container),
  :global(.app-main),
  .entrust-page {
    display: block;
    padding: 0;
    margin: 0;
    width: 100%;
    min-height: 0;
    background: #ffffff !important;
  }

  :global(.app-main) {
    --el-main-padding: 0;
    padding: 0 !important;
  }

  .print-sheet {
    max-width: none;
    width: 100%;
    margin: 0 auto;
    padding: 0;
    border: 0;
    box-shadow: none;
    font-size: 9.6px;
  }

  .sheet-header {
    margin-bottom: 5px;
  }

  .sheet-meta {
    display: flex;
    justify-content: space-between;
    margin-bottom: 2px;
    font-size: 8.8px;
    line-height: 1;
  }

  .sheet-header h1 {
    font-size: 22px;
    line-height: 1;
  }

  .sheet-header h2 {
    margin-top: 3px;
    font-size: 15px;
    line-height: 1;
  }

  th,
  td {
    min-height: 0;
    padding: 4.5px 5px;
    font-size: 9.1px;
    line-height: 1.15;
  }

  .warrant-table th,
  .warrant-table td {
    height: 24px;
    padding: 3px 4px;
    font-size: 8.9px;
  }

  .warrant-layout-title th {
    height: 28px;
    font-size: 17px;
  }

  .warrant-layout-cell {
    padding: 4px 5px 2px;
  }

  .layout-box.warrant-layout-box {
    gap: 4px;
    min-height: 314px;
    margin: 0;
  }

  .warrant-layout-box .layout-core {
    grid-template-rows: 58px 1fr 56px;
    height: 294px;
    box-sizing: border-box;
    padding-right: 0;
    padding-bottom: 28px;
  }

  .warrant-layout-box .layout-window {
    min-height: 196px;
  }

  .warrant-layout-box .layout-bottom {
    font-size: 7.8px;
  }

  .layout-formula-table {
    display: grid !important;
    gap: 1px;
    font-size: 8.4px;
    line-height: 1;
  }

  .layout-formula-table > div {
    grid-template-columns: 108px minmax(0, 1fr) 52px;
    gap: 5px;
    min-height: 13px;
    border-top: 1.5px solid #111827;
  }

  .layout-near-label {
    min-width: 24px;
    padding: 0 2px;
    font-size: 7.8px;
  }

  .warrant-layout-box .layout-near-label {
    display: none;
  }

  .warrant-layout-box .layout-top {
    display: block;
    padding: 0 8px;
    font-size: 8px;
  }

  .warrant-layout-box .layout-top-guide {
    min-width: 28px;
    padding: 0 2px;
  }

  .warrant-layout-box .layout-top-guide::after {
    height: 9px;
  }

  .warrant-layout-box .layout-top-guide::before {
    top: calc(100% + 9px);
    border-right-width: 3px;
    border-left-width: 3px;
    border-top-width: 5px;
  }

  .warrant-layout-box .layout-added-side_pattern_mark_stack,
  .warrant-layout-box .layout-added-side_pattern_mark_stack_right,
  .warrant-layout-box .layout-side-pattern-stack {
    width: 34px;
    height: 96px;
  }

  .warrant-layout-box .layout-added-side_pattern_text {
    font-size: 7.2px;
  }

  .layout-dimension-arrow {
    font-size: 7.4px;
  }

  .layout-dimension-arrow strong {
    padding: 0 2px;
  }

  .dimension-line.horizontal {
    border-top-width: 1px;
  }

  .dimension-line.vertical {
    border-left-width: 1px;
  }

  .dimension-line.horizontal::before,
  .dimension-line.horizontal::after {
    top: -3px;
    border-top-width: 3px;
    border-bottom-width: 3px;
  }

  .dimension-line.horizontal::before {
    border-right-width: 5px;
  }

  .dimension-line.horizontal::after {
    border-left-width: 5px;
  }

  .dimension-line.vertical::before,
  .dimension-line.vertical::after {
    left: -3.5px;
    border-right-width: 3px;
    border-left-width: 3px;
  }

  .dimension-line.vertical::before {
    border-bottom-width: 5px;
  }

  .dimension-line.vertical::after {
    border-top-width: 5px;
  }

  .cir-dimension {
    top: 6px;
    right: 5px;
    bottom: 6px;
    width: 30px;
    grid-template-columns: minmax(0, 1fr) 8px;
    gap: 2px;
  }

  .width-dimension {
    bottom: -28px;
    height: 20px;
    grid-template-rows: 7px 12px;
  }

  .layout-edge-ticks {
    height: 6px;
  }

  .layout-edge-ticks i {
    width: 1px;
    height: 6px;
  }

  .screen-info-table {
    display: table;
    table-layout: fixed;
  }

  .portrait-info-table {
    display: none;
  }

  .color-table,
  .requirement-table {
    margin-top: 4px;
  }

  .layout-title {
    margin: 8px 0 4px;
    font-size: 19px;
  }

  .layout-box {
    break-inside: avoid;
    min-height: 300px;
    margin: 0 0 8px;
  }

  .layout-core {
    grid-template-rows: 48px 1fr 56px;
    height: 300px;
  }

  .layout-window {
    min-height: 196px;
  }

  .layout-section-full {
    min-height: 196px;
    padding: 12px;
    font-size: 21px;
  }

  .layout-top,
  .layout-bottom {
    gap: 9px;
    font-size: 8px;
    line-height: 1;
  }

  .middle-grid {
    min-height: 0;
  }

  .middle-grid-value {
    font-size: 18px;
  }

  .layout-added-item {
    font-size: 15px;
  }

  .requirement-table th {
    width: 70px;
  }

  .requirement-table td {
    height: 42px;
    padding: 6px 8px;
  }

  .color-table th:first-child,
  .color-table td:first-child {
    width: 58px;
  }

  .color-table th:last-child,
  .color-table td:last-child {
    width: 42px;
  }
}
</style>
