import { describe, it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import Loading from "@/components/common/Loading.vue"
import EmptyState from "@/components/common/EmptyState.vue"
import ErrorState from "@/components/common/ErrorState.vue"

// Element Plus stubs for lightweight rendering
const stubs = {
  "el-skeleton": { template: "<div class='el-skeleton-stub'><slot /></div>", props: ["rows", "animated"] },
  "el-empty": { template: "<div class='el-empty-stub'><slot /></div>", props: ["description"] },
  "el-button": { template: "<button class='el-button-stub'><slot /></button>" },
  "el-result": { template: "<div class='el-result-stub'><slot /><slot name='extra' /></div>", props: ["icon", "title", "sub-title"] },
}

describe("Loading.vue", () => {
  it("renders skeleton when loading is true", () => {
    const wrapper = mount(Loading, {
      props: { loading: true, rows: 3 },
      global: { stubs },
    })
    expect(wrapper.find(".el-skeleton-stub").exists()).toBe(true)
  })

  it("renders slot content when loading is false", () => {
    const wrapper = mount(Loading, {
      props: { loading: false },
      slots: { default: "<p class='content'>loaded</p>" },
      global: { stubs },
    })
    expect(wrapper.find(".content").exists()).toBe(true)
    expect(wrapper.find(".content").text()).toBe("loaded")
  })

  it("does not render skeleton when loading is false", () => {
    const wrapper = mount(Loading, {
      props: { loading: false },
      slots: { default: "<p>content</p>" },
      global: { stubs },
    })
    expect(wrapper.find(".el-skeleton-stub").exists()).toBe(false)
  })
})

describe("EmptyState.vue", () => {
  it("renders empty state when not loading and data is empty array", () => {
    const wrapper = mount(EmptyState, {
      props: { loading: false, data: [], description: "暂无数据" },
      global: { stubs },
    })
    expect(wrapper.find(".el-empty-stub").exists()).toBe(true)
  })

  it("renders empty state when data is null", () => {
    const wrapper = mount(EmptyState, {
      props: { loading: false, data: null },
      global: { stubs },
    })
    expect(wrapper.find(".el-empty-stub").exists()).toBe(true)
  })

  it("renders slot content when data is non-empty", () => {
    const wrapper = mount(EmptyState, {
      props: { loading: false, data: [1, 2, 3] },
      slots: { default: "<p class='content'>has data</p>" },
      global: { stubs },
    })
    expect(wrapper.find(".content").exists()).toBe(true)
  })

  it("renders slot content when loading is true", () => {
    const wrapper = mount(EmptyState, {
      props: { loading: true, data: [] },
      slots: { default: "<p class='content'>loading</p>" },
      global: { stubs },
    })
    expect(wrapper.find(".content").exists()).toBe(true)
  })

  it("shows action button when actionText is provided", () => {
    const wrapper = mount(EmptyState, {
      props: { loading: false, data: [], actionText: "添加" },
      global: { stubs },
    })
    expect(wrapper.find(".el-button-stub").exists()).toBe(true)
    expect(wrapper.find(".el-button-stub").text()).toBe("添加")
  })

  it("emits action event when button is clicked", async () => {
    const wrapper = mount(EmptyState, {
      props: { loading: false, data: [], actionText: "添加" },
      global: { stubs },
    })
    await wrapper.find(".el-button-stub").trigger("click")
    expect(wrapper.emitted("action")).toBeTruthy()
    expect(wrapper.emitted("action")!.length).toBe(1)
  })
})

describe("ErrorState.vue", () => {
  it("renders error state when error is true", () => {
    const wrapper = mount(ErrorState, {
      props: { error: true, message: "出错了" },
      global: { stubs },
    })
    expect(wrapper.find(".el-result-stub").exists()).toBe(true)
  })

  it("renders slot content when error is false", () => {
    const wrapper = mount(ErrorState, {
      props: { error: false },
      slots: { default: "<p class='content'>no error</p>" },
      global: { stubs },
    })
    expect(wrapper.find(".content").exists()).toBe(true)
  })

  it("shows retry button", () => {
    const wrapper = mount(ErrorState, {
      props: { error: true },
      global: { stubs },
    })
    expect(wrapper.find(".el-button-stub").exists()).toBe(true)
  })

  it("emits retry event when button is clicked", async () => {
    const wrapper = mount(ErrorState, {
      props: { error: true },
      global: { stubs },
    })
    await wrapper.find(".el-button-stub").trigger("click")
    expect(wrapper.emitted("retry")).toBeTruthy()
    expect(wrapper.emitted("retry")!.length).toBe(1)
  })

  it("displays custom error message", () => {
    const wrapper = mount(ErrorState, {
      props: { error: true, message: "网络连接失败" },
      global: { stubs },
    })
    // The message is passed as sub-title prop to el-result
    expect(wrapper.props("message")).toBe("网络连接失败")
  })
})
