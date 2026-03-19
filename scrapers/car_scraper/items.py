import scrapy


class IssueReferenceItem(scrapy.Item):
    source = scrapy.Field()
    source_url = scrapy.Field()
    make = scrapy.Field()
    model = scrapy.Field()
    generation = scrapy.Field()
    year_start = scrapy.Field()
    year_end = scrapy.Field()
    issue_domain = scrapy.Field()
    severity = scrapy.Field()
    title = scrapy.Field()
    symptoms = scrapy.Field()
    details = scrapy.Field()
    recommendation = scrapy.Field()
