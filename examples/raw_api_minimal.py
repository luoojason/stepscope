import stepscope

stepscope.init(local=True)

with stepscope.step("hello"):
    pass

with stepscope.step("world"):
    pass

# View results: stepscope funnel ./stepscope.db --since all
