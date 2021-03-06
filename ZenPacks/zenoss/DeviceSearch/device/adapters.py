##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2010, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


from zope.component import adapts
from zope.interface import implements
from Products.AdvancedQuery import MatchGlob, And, Or, RankByQueries_Sum
from Products.ZenModel.DataRoot import DataRoot
from Products.Zuul.search import ISearchProvider
from Products.Zuul.search import ISearchResult
from Products.Zuul import checkPermission

try:
    from Products.Zuul.catalog.interfaces import IModelCatalogTool

    USE_MODEL_CATALOG = True
except ImportError:
    USE_MODEL_CATALOG = False

class DeviceSearchProvider(object):
    """
    Provider which searches Zenoss's global catalog for matching devices
    """
    implements(ISearchProvider)
    adapts(DataRoot)

    def __init__(self, dmd):
        self._dmd = dmd

    def getCategoryCounts(self, parsedQuery, filterFn=None):
        return self.getSearchResults(parsedQuery, countOnly=True, filterFn=filterFn)

    def _getSearchResultsFromModelCatalog(self, parsedQuery, sorter=None, category=None, countOnly=False,
                                          unrestricted=False, filterFn=None, maxResults=None):
        operators = parsedQuery.operators
        keywords = parsedQuery.keywords

        if not keywords:
            return

        def listMatchGlob(op, index, list):
            return op(*[MatchGlob(index, '*%s*' % i) for i in list])

        dmd = self._dmd

        kw_query = Or(listMatchGlob(And, 'name', keywords),
                      listMatchGlob(And, 'text_ipAddress', keywords))

        # Rank devices whose name match the query higher than other stuff
        # TODO: Figure out how to expose Lucene boosts
        # For now we just or the boost query in with the original query to boost those results
        ranker = listMatchGlob(Or, 'name', keywords)
        full_query = Or(kw_query, ranker)
        cat = IModelCatalogTool(dmd).devices
        limit = 0 if countOnly and not filterFn else maxResults
        # Set orderby to None so that modelindex will rank by score
        catalogItems = cat.search(query=full_query, orderby=None, filterPermissions=True, limit=limit)
        brainResults = [DeviceSearchResult(catalogItem) for catalogItem in catalogItems]

        if countOnly and not filterFn:
            return dict(Device=brainResults.total)

        if filterFn:
            brainResults = filter(filterFn, brainResults)

        if countOnly:
            return dict(Device=len(brainResults))
        results = brainResults

        if sorter is not None:
            results = sorter.limitSort(results)

        return results

    def _getSearchResultsFromDeviceSearchCatalog(self, parsedQuery, sorter=None, category=None, countOnly=False,
                                          unrestricted=False, filterFn=None, maxResults=None):
        """
        DEPRECATED.  the DeviceSearch catalog will be replaced by the Model Catalog
        """
        operators = parsedQuery.operators
        keywords = parsedQuery.keywords

        if not keywords:
            return

        def listMatchGlob(op, index, list):
            return op(*[MatchGlob(index, '*%s*' % i) for i in list])

        dmd = self._dmd

        kw_query = Or(listMatchGlob(And, 'titleOrId', keywords),
                      listMatchGlob(And, 'getDeviceIp', keywords))

        # Rank devices whose name match the query higher than other stuff
        ranker = RankByQueries_Sum((listMatchGlob(Or, 'titleOrId', keywords), 10), )
        full_query = kw_query
        cat = dmd.Devices.deviceSearch
        querySet = full_query
        catalogItems = cat.evalAdvancedQuery(querySet, (ranker,))
        brainResults = [DeviceSearchResult(catalogItem)
                        for catalogItem in catalogItems if checkPermission("View", catalogItem.getObject())]

        if filterFn:
            brainResults = filter(filterFn, brainResults)

        if countOnly:
            return dict(Device=len(brainResults))
        results = brainResults

        if sorter is not None:
            results = sorter.limitSort(results)

        return results

    def getSearchResults(self, parsedQuery, sorter=None, category=None, countOnly=False,
                         unrestricted=False, filterFn=None, maxResults=None):
        """
        Queries the catalog.  Searches the searchKeywords index
        using *keyword1* AND *keyword2* AND so on.
        If there are preferred categories, find maxResults # of instances
        before searching other categories.

        @rtype generator of BrainSearchResult objects
        """
        if USE_MODEL_CATALOG:
            return self._getSearchResultsFromModelCatalog(parsedQuery, sorter, category, countOnly, unrestricted,
                                                          filterFn, maxResults)
        else:
            return self._getSearchResultsFromDeviceSearchCatalog(parsedQuery, sorter, category, countOnly, unrestricted,
                                                          filterFn, maxResults)

    def getQuickSearchResults(self, parsedQuery, maxResults=None):
        """
        Currently just calls getSearchResults
        """
        return self.getSearchResults(parsedQuery, maxResults)


class DeviceSearchResult(object):
    """
    Wraps a brain from the search catalog for inclusion in search results.
    """

    implements(ISearchResult)

    def __init__(self, brain):
        self._brain = brain

    @property
    def url(self):
        return self._brain.getPath()

    @property
    def category(self):
        return self._brain.meta_type

    @property
    def excerpt(self):
        return self._brain.id

    @property
    def iconTemplate(self):
        return "<img src='%s' />" % self._brain.getObject().zIcon

    @property
    def icon(self):
        # show no icon so we don't have to wake up the object
        return self.iconTemplate

    @property
    def popout(self):
        return False
