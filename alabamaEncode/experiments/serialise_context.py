from alabamaEncode.core.context import AlabamaContext

if __name__ == "__main__":
    ctx = AlabamaContext()

    ctx.use_celery = "KAWAI"

    json = ctx.to_json()

    print(json)

    from_json = AlabamaContext().from_json(json)

    print(from_json)
